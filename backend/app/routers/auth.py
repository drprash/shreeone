from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from collections import defaultdict, deque
from threading import Lock
import time
import uuid
import json
import logging

logger = logging.getLogger(__name__)
from app import schemas, models, crud, auth
from app.database import get_db
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()
_rate_limit_lock = Lock()
_login_rate_buckets = defaultdict(deque)
_refresh_rate_buckets = defaultdict(deque)
_login_rate_last_seen = {}
_refresh_rate_last_seen = {}


def _request_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune_rate_limit_store(bucket_store: dict, last_seen_store: dict, now: float, window_seconds: int):
    if len(last_seen_store) <= settings.rate_limit_max_keys:
        return

    stale_before = now - max(window_seconds * 2, 3600)
    stale_keys = [
        candidate_key
        for candidate_key, last_seen in last_seen_store.items()
        if last_seen < stale_before
    ]

    if not stale_keys:
        stale_keys = sorted(last_seen_store, key=last_seen_store.get)[: settings.rate_limit_prune_batch_size]
    else:
        stale_keys = stale_keys[: settings.rate_limit_prune_batch_size]

    for stale_key in stale_keys:
        bucket_store.pop(stale_key, None)
        last_seen_store.pop(stale_key, None)


def _enforce_rate_limit(
    bucket_store: dict,
    last_seen_store: dict,
    key: str,
    limit: int,
    window_seconds: int,
):
    now = time.time()
    window_start = now - window_seconds
    with _rate_limit_lock:
        _prune_rate_limit_store(bucket_store, last_seen_store, now, window_seconds)
        bucket = bucket_store[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )
        bucket.append(now)
        last_seen_store[key] = now


def _issue_token_pair(db: Session, user: models.User):
    """Issue access + refresh token pair and persist the refresh token JTI."""
    jti = str(uuid.uuid4())
    access_token, _ = auth.create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    refresh_token_str = auth.create_refresh_token(
        data={"sub": str(user.id), "v": user.token_version},
        jti=jti
    )
    crud.store_refresh_token(db, jti, user.id, user.token_version, expires_at)
    return access_token, refresh_token_str


def _rp_id_from_request(request: Request) -> str:
    """
    Return the WebAuthn RP ID (domain only, no port).
    Derived from FRONTEND_URL so it matches the public-facing domain even
    when running behind a reverse proxy.
    """
    from urllib.parse import urlparse
    return urlparse(settings.frontend_url).hostname or "localhost"


def _origin_from_request(request: Request) -> str:
    """
    Return the WebAuthn expected origin.
    Uses FRONTEND_URL from config (already set to the public-facing URL, e.g.
    https://shreeone.com) so it is always correct even when SSL terminates at
    a reverse proxy and the backend only sees plain HTTP.
    """
    from urllib.parse import urlparse
    parsed = urlparse(settings.frontend_url)
    # origin = scheme + host (host already includes port when non-standard)
    return f"{parsed.scheme}://{parsed.netloc}"


@router.post("/register", response_model=schemas.Token)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    if not user_data.family_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Family name required for registration"
        )

    family = crud.create_family(db, schemas.FamilyCreate(
        name=user_data.family_name,
        base_currency=user_data.base_currency or "USD"
    ))

    user = crud.create_user(
        db=db,
        user=user_data,
        family_id=family.id,
        role=models.Role.ADMIN,
        activated=True,
        password_required=False
    )

    crud.create_member_permission(
        db=db,
        family_id=family.id,
        perm=schemas.MemberPermissionCreate(
            user_id=user.id,
            can_add_transaction=True,
            can_edit_transaction=True,
            can_delete_transaction=True,
            can_add_account=True,
            can_edit_account=True,
            can_delete_account=True,
            can_manage_categories=True,
            can_view_all_accounts=True,
            can_view_all_transactions=True,
        )
    )

    crud.create_audit_log(
        db=db,
        user_id=user.id,
        action="FAMILY_CREATED",
        entity_type="Family",
        entity_id=family.id,
        new_values=f"Created family '{family.name}' with admin {user.email}"
    )

    access_token, refresh_token = _issue_token_pair(db, user)
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=schemas.UserResponse.model_validate(user)
    )


@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = _request_ip(request)
    key = f"{ip}:{credentials.email.lower()}"
    _enforce_rate_limit(
        _login_rate_buckets,
        _login_rate_last_seen,
        key,
        settings.login_rate_limit_attempts,
        settings.login_rate_limit_window_seconds,
    )

    user = crud.get_user_by_email(db, credentials.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if user.password_required or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must set your password first using the activation token"
        )

    if not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    access_token, refresh_token = _issue_token_pair(db, user)
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=schemas.UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=schemas.Token)
def refresh_token(token_data: schemas.TokenRefresh, request: Request, db: Session = Depends(get_db)):
    ip = _request_ip(request)
    _enforce_rate_limit(
        _refresh_rate_buckets,
        _refresh_rate_last_seen,
        ip,
        settings.refresh_rate_limit_requests,
        settings.refresh_rate_limit_window_seconds,
    )

    payload = auth.decode_token(token_data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    user = crud.get_user(db, user_id)
    if not user or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    token_version = payload.get("v", 0)
    if token_version != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been invalidated"
        )

    jti = payload.get("jti")
    if not jti or not crud.consume_refresh_token(db, jti):
        # Token reuse detected — invalidate ALL tokens for this user
        crud.bump_user_token_version(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected. All sessions have been invalidated."
        )

    access_token, refresh_token_str = _issue_token_pair(db, user)
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token_str,
        user=schemas.UserResponse.model_validate(user)
    )


@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@router.post("/verify-activation-token", response_model=schemas.ActivationTokenVerification)
def verify_activation_token(token: str, db: Session = Depends(get_db)):
    """Verify if an activation token is valid (exists, not expired, not used)."""
    is_valid, db_token = crud.verify_activation_token(db, token)

    if not is_valid:
        return schemas.ActivationTokenVerification(valid=False)

    user = crud.get_user(db, db_token.user_id)
    return schemas.ActivationTokenVerification(
        valid=True,
        expires_at=db_token.expires_at,
        user_email=user.email if user else None
    )


@router.post("/forgot-password", response_model=schemas.PasswordResetTokenResponse)
def forgot_password(request: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, request.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is deactivated"
        )

    reset_token = crud.create_activation_token(db, user.id, activation_token_hours=72)

    crud.create_audit_log(
        db=db,
        user_id=user.id,
        action="PASSWORD_RESET_REQUESTED",
        entity_type="User",
        entity_id=user.id,
        new_values=f"Password reset token generated for {user.email}"
    )

    return schemas.PasswordResetTokenResponse(
        token=reset_token.token,
        expires_at=reset_token.expires_at,
        user_email=user.email
    )


@router.post("/set-password", response_model=schemas.Token)
def set_password(password_data: schemas.SetPasswordRequest, db: Session = Depends(get_db)):
    is_valid, db_token = crud.verify_activation_token(db, password_data.activation_token)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token"
        )

    user = crud.set_user_password_from_token(db, password_data.activation_token, password_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to set password. User not found or token invalid."
        )

    # Invalidate all previously issued refresh tokens for this user
    crud.bump_user_token_version(db, user)

    access_token, refresh_token = _issue_token_pair(db, user)
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=schemas.UserResponse.model_validate(user)
    )


# ============ WebAuthn / Biometric ============

@router.post("/webauthn/register/begin")
def webauthn_register_begin(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        UserVerificationRequirement,
        ResidentKeyRequirement,
    )
    import base64

    rp_id = _rp_id_from_request(request)
    existing = crud.get_webauthn_credentials(db, current_user.id)
    exclude_credentials = [
        {"id": base64.urlsafe_b64decode(c.credential_id + "=="), "type": "public-key"}
        for c in existing
    ]

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=settings.app_name,
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.full_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=exclude_credentials,
    )

    challenge_b64 = base64.urlsafe_b64encode(options.challenge).rstrip(b"=").decode()
    crud.store_webauthn_challenge(db, current_user.id, challenge_b64, "registration")

    return JSONResponse(content=json.loads(options_to_json(options)))


@router.post("/webauthn/register/complete", response_model=schemas.WebAuthnCredentialResponse)
def webauthn_register_complete(
    body: schemas.WebAuthnRegisterCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    from webauthn import verify_registration_response
    from webauthn.helpers.structs import RegistrationCredential, AuthenticatorAttestationResponse
    from webauthn.helpers import base64url_to_bytes
    import base64

    challenge_b64 = crud.consume_webauthn_challenge(db, current_user.id, "registration")
    if not challenge_b64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge expired or not found")

    challenge_bytes = base64.urlsafe_b64decode(challenge_b64 + "==")
    rp_id = _rp_id_from_request(request)
    origin = _origin_from_request(request)

    credential = RegistrationCredential(
        id=body.credential_id,
        raw_id=base64url_to_bytes(body.credential_id),
        response=AuthenticatorAttestationResponse(
            client_data_json=base64url_to_bytes(body.client_data_json),
            attestation_object=base64url_to_bytes(body.attestation_object),
        ),
        type="public-key",
    )

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge_bytes,
            expected_rp_id=rp_id,
            expected_origin=origin,
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Registration failed: {str(e)}")

    public_key_b64 = base64.urlsafe_b64encode(verification.credential_public_key).rstrip(b"=").decode()
    cred = crud.store_webauthn_credential(
        db=db,
        user_id=current_user.id,
        credential_id=body.credential_id,
        public_key=public_key_b64,
        sign_count=verification.sign_count,
        device_name=body.device_name,
    )
    return cred


@router.get("/webauthn/credentials", response_model=list[schemas.WebAuthnCredentialResponse])
def webauthn_list_credentials(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return crud.get_webauthn_credentials(db, current_user.id)


@router.delete("/webauthn/credentials/{credential_id}", status_code=204)
def webauthn_delete_credential(
    credential_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    deleted = crud.delete_webauthn_credential(db, credential_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")


@router.post("/webauthn/auth/begin")
def webauthn_auth_begin(
    body: schemas.WebAuthnAuthBeginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement, PublicKeyCredentialDescriptor, PublicKeyCredentialType
    from webauthn.helpers import base64url_to_bytes
    import base64

    user = crud.get_user(db, body.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    credentials = crud.get_webauthn_credentials(db, user.id)
    if not credentials:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No passkeys registered for this user")

    try:
        allow_credentials = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id), type=PublicKeyCredentialType.PUBLIC_KEY)
            for c in credentials
        ]

        rp_id = _rp_id_from_request(request)
        options = generate_authentication_options(
            rp_id=rp_id,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.REQUIRED,
        )

        challenge_b64 = base64.urlsafe_b64encode(options.challenge).rstrip(b"=").decode()
        crud.store_webauthn_challenge(db, user.id, challenge_b64, "authentication")

        return JSONResponse(content=json.loads(options_to_json(options)))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("webauthn_auth_begin failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to begin passkey authentication: {str(e)}")


@router.post("/webauthn/auth/complete", response_model=schemas.Token)
def webauthn_auth_complete(
    body: schemas.WebAuthnAuthCompleteRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    from webauthn import verify_authentication_response
    from webauthn.helpers.structs import AuthenticationCredential, AuthenticatorAssertionResponse
    from webauthn.helpers import base64url_to_bytes
    import base64

    user = crud.get_user(db, body.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    challenge_b64 = crud.consume_webauthn_challenge(db, user.id, "authentication")
    if not challenge_b64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge expired or not found")

    challenge_bytes = base64.urlsafe_b64decode(challenge_b64 + "==")

    db_cred = crud.get_webauthn_credential_by_id(db, body.credential_id)
    if not db_cred or str(db_cred.user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credential not found")

    rp_id = _rp_id_from_request(request)
    origin = _origin_from_request(request)

    try:
        public_key_bytes = base64.urlsafe_b64decode(db_cred.public_key + "==")

        credential = AuthenticationCredential(
            id=body.credential_id,
            raw_id=base64url_to_bytes(body.credential_id),
            response=AuthenticatorAssertionResponse(
                client_data_json=base64url_to_bytes(body.client_data_json),
                authenticator_data=base64url_to_bytes(body.authenticator_data),
                signature=base64url_to_bytes(body.signature),
                user_handle=base64url_to_bytes(body.user_handle) if body.user_handle else None,
            ),
            type="public-key",
        )

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge_bytes,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=public_key_bytes,
            credential_current_sign_count=db_cred.sign_count,
            require_user_verification=True,
        )
    except Exception as e:
        logger.exception("webauthn_auth_complete failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication failed: {str(e)}")

    crud.update_webauthn_sign_count(db, db_cred, verification.new_sign_count)

    access_token, refresh_token = _issue_token_pair(db, user)
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=schemas.UserResponse.model_validate(user)
    )
