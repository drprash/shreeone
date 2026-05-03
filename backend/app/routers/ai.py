"""
AI Router — endpoints for local AI features (Ollama / Gemma 4 E4B).

All endpoints degrade gracefully if the LLM service is unavailable.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app import auth, crud, models, schemas
from app.database import get_db
from app.services import ai_service
from app.services.llm_backends.factory import build_backend_for_provider, get_configured_providers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

def _get_ai_prefs(db: Session, family_id: UUID) -> models.FamilyPreference:
    prefs = db.query(models.FamilyPreference).filter(
        models.FamilyPreference.family_id == family_id
    ).first()
    return prefs


def _require_feature(prefs: Optional[models.FamilyPreference], flag: str):
    if prefs is None:
        return  # no prefs row → default enabled
    if not getattr(prefs, flag, True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"AI feature '{flag}' is disabled for this family."
        )


def _require_ai_enabled(prefs: Optional[models.FamilyPreference]):
    if prefs is None:
        return  # no prefs row → default enabled
    if not prefs.ai_services_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI services are disabled for this family."
        )


@router.get("/status", response_model=schemas.AIStatusResponse)
def ai_status(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return AI service availability, per-family feature flags, and provider info."""
    from app.services.llm_backends.factory import get_backend, get_effective_provider
    from app.config import settings as app_settings

    available = ai_service.is_available(family_id=current_user.family_id, db=db)
    prefs = _get_ai_prefs(db, current_user.family_id)

    def flag(name: str) -> bool:
        if prefs is None:
            return True
        return bool(getattr(prefs, name, True))

    effective_provider = get_effective_provider(family_id=current_user.family_id, db=db)
    backend = get_backend(family_id=current_user.family_id, db=db)
    effective_model = getattr(backend, "model", "")

    return schemas.AIStatusResponse(
        ai_service_available=available,
        ai_services_enabled=bool(prefs.ai_services_enabled) if prefs is not None else True,
        ai_categorization_enabled=flag("ai_categorization_enabled"),
        ai_monthly_narrative_enabled=flag("ai_monthly_narrative_enabled"),
        ai_weekly_digest_enabled=flag("ai_weekly_digest_enabled"),
        ai_receipt_ocr_enabled=flag("ai_receipt_ocr_enabled"),
        ai_voice_entry_enabled=flag("ai_voice_entry_enabled"),
        ai_statement_upload_enabled=flag("ai_statement_upload_enabled"),
        ai_provider=effective_provider,
        ai_model=effective_model,
        configured_providers=get_configured_providers(app_settings),
    )

def _format_provider_error(provider: str, exc: Exception) -> str:
    msg = str(exc).lower()
    if provider == "local" and ("connection refused" in msg or "connect" in msg):
        return "Ollama is not running — start with: docker compose --profile ollama up -d"
    if "invalid" in msg and "key" in msg:
        return "Invalid API key"
    if "timeout" in msg or "timed out" in msg:
        return "Connection timed out"
    if "authentication" in msg or "auth" in msg:
        return "Invalid API key"
    return f"Connection failed: {str(exc)}"


@router.post("/test-connection", response_model=schemas.AITestConnectionResponse)
def test_connection(
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Test all server-configured AI providers. Admin only. No state saved."""
    from app.config import settings as app_settings

    configured = get_configured_providers(app_settings)
    results = []

    for provider in configured:
        try:
            backend = build_backend_for_provider(provider)
            raw = backend.complete("Hi", max_tokens=1)
            success = raw is not None
            error = None if success else "No response from provider"
        except Exception as exc:
            success = False
            error = _format_provider_error(provider, exc)
        results.append(schemas.AIProviderTestResult(
            provider=provider,
            success=success,
            error=error,
        ))

    return schemas.AITestConnectionResponse(results=results)


@router.post("/categorize", response_model=schemas.CategorizationResponse)
def categorize_transaction(
    payload: schemas.CategorizationRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Suggest a category for a transaction description."""
    prefs = _get_ai_prefs(db, current_user.family_id)
    _require_ai_enabled(prefs)
    _require_feature(prefs, "ai_categorization_enabled")

    if not ai_service.is_available(family_id=current_user.family_id, db=db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not available."
        )

    # Fetch this family's active categories
    categories = db.query(models.Category).filter(
        models.Category.family_id == current_user.family_id,
        models.Category.deleted_at.is_(None),
    ).all()
    category_names = [c.name for c in categories]

    result = ai_service.categorize_transaction(
        payload.description, category_names,
        family_id=current_user.family_id, db=db,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not determine category."
        )

    # Resolve category_id from name
    matched = next((c for c in categories if c.name == result["category"]), None)
    return schemas.CategorizationResponse(
        category=result["category"],
        category_id=matched.id if matched else None,
        confidence=result.get("confidence", "medium"),
    )

@router.post("/parse-receipt", response_model=schemas.ReceiptParseResponse)
async def parse_receipt(
    image: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a receipt image → pre-filled transaction draft.
    Accepts JPEG, PNG, WEBP.
    """
    prefs = _get_ai_prefs(db, current_user.family_id)
    _require_ai_enabled(prefs)
    _require_feature(prefs, "ai_receipt_ocr_enabled")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type '{image.content_type}'. Use JPEG, PNG, or WEBP."
        )

    # 10 MB limit
    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large. Maximum size is 10 MB."
        )

    if not ai_service.is_available(family_id=current_user.family_id, db=db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not available."
        )

    result = ai_service.parse_receipt(
        content, image.content_type,
        family_id=current_user.family_id, db=db,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse the image as a receipt."
        )

    return schemas.ReceiptParseResponse(
        is_receipt=result.get("is_receipt", False),
        merchant=result.get("merchant"),
        amount=result.get("amount"),
        currency=result.get("currency"),
        date=result.get("date"),
        category_hint=result.get("category_hint"),
    )

@router.post("/parse-voice", response_model=schemas.VoiceParseResponse)
async def parse_voice(
    audio: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a voice clip → pre-filled transaction draft.
    Accepts webm, ogg, mp4, wav.
    """
    prefs = _get_ai_prefs(db, current_user.family_id)
    _require_ai_enabled(prefs)
    _require_feature(prefs, "ai_voice_entry_enabled")

    allowed_types = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}
    if audio.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio type '{audio.content_type}'."
        )

    # 25 MB limit
    content = await audio.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file too large. Maximum size is 25 MB."
        )

    if not ai_service.is_available(family_id=current_user.family_id, db=db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not available."
        )

    result = ai_service.parse_voice(content, audio.content_type)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract a transaction from the audio."
        )

    return schemas.VoiceParseResponse(
        is_transaction=result.get("is_transaction", False),
        amount=result.get("amount"),
        currency=result.get("currency"),
        description=result.get("description"),
        category_hint=result.get("category_hint"),
    )

@router.post("/parse-voice-text", response_model=schemas.VoiceParseResponse)
def parse_voice_text(
    payload: schemas.VoiceTranscriptRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Parse a plain-text voice transcript (produced by the browser's Web Speech API)
    and extract a transaction draft using the LLM.
    """
    prefs = _get_ai_prefs(db, current_user.family_id)
    _require_ai_enabled(prefs)
    _require_feature(prefs, "ai_voice_entry_enabled")

    if not ai_service.is_available(family_id=current_user.family_id, db=db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not available."
        )

    result = ai_service.parse_voice_transcript(
        payload.transcript,
        family_id=current_user.family_id, db=db,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract a transaction from the voice transcript."
        )

    return schemas.VoiceParseResponse(
        is_transaction=result.get("is_transaction", False),
        amount=result.get("amount"),
        currency=result.get("currency"),
        description=result.get("description"),
        category_hint=result.get("category_hint"),
    )

@router.post("/parse-statement", response_model=schemas.StatementParseResponse)
async def parse_statement(
    file: UploadFile = File(...),
    account_id: str = None,
    account_type: str = "BANK",
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a bank or credit-card statement (PDF or image) → list of expense transactions.

    account_type: "BANK" or "CREDIT_CARD"
    Returns StatementParseResponse for the frontend preview table.
    """
    from fastapi import Form as FastAPIForm
    prefs = _get_ai_prefs(db, current_user.family_id)
    _require_ai_enabled(prefs)
    _require_feature(prefs, "ai_statement_upload_enabled")

    allowed_types = {
        "application/pdf",
        "image/jpeg", "image/png", "image/webp",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{file.content_type}'. Use PDF, JPEG, PNG, or WEBP."
        )

    if account_type not in ("BANK", "CREDIT_CARD"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_type must be BANK or CREDIT_CARD."
        )

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 20 MB."
        )

    if not ai_service.is_available(family_id=current_user.family_id, db=db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not available."
        )

    rows = ai_service.parse_statement(
        content, file.content_type, account_type,
        family_id=current_user.family_id, db=db,
    )
    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract transactions from the statement."
        )

    # Duplicate detection: flag rows where (account_id, date, amount) already exist
    parsed_account_id = None
    if account_id:
        try:
            from uuid import UUID as _UUID
            parsed_account_id = _UUID(account_id)
        except ValueError:
            pass

    existing_keys: set = set()
    if parsed_account_id:
        from app import models as _models
        from datetime import datetime as _dt
        existing = db.query(
            _models.Transaction.transaction_date,
            _models.Transaction.amount,
        ).filter(
            _models.Transaction.account_id == parsed_account_id,
            _models.Transaction.deleted_at.is_(None),
        ).all()
        for tx in existing:
            existing_keys.add((str(tx.transaction_date)[:10], float(tx.amount)))

    transactions = []
    for row in rows:
        date_str = row.get("date", "")
        amount = row.get("amount")
        is_dup = (date_str, float(amount)) in existing_keys if amount else False

        # Best-effort category hint via AI
        description = row.get("description", "")
        category_hint = None
        if description:
            categories = db.query(models.Category).filter(
                models.Category.family_id == current_user.family_id,
                models.Category.deleted_at.is_(None),
                models.Category.type == "EXPENSE",
            ).all()
            cat_result = ai_service.categorize_transaction(
                description, [c.name for c in categories],
                family_id=current_user.family_id, db=db,
            )
            if cat_result:
                category_hint = cat_result.get("category")

        transactions.append(schemas.StatementTransaction(
            date=date_str or None,
            description=description or None,
            amount=amount,
            category_hint=category_hint,
            duplicate=is_dup,
        ))

    return schemas.StatementParseResponse(
        transactions=transactions,
        raw_count=len(rows),
    )

@router.get("/narratives", response_model=list[schemas.AINarrativeResponse])
def get_narratives(
    narrative_type: Optional[str] = None,
    limit: int = 5,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """List AI-generated narratives for this family (monthly / weekly)."""
    query = db.query(models.AINarrative).filter(
        models.AINarrative.family_id == current_user.family_id,
        models.AINarrative.dismissed_at.is_(None),
    )
    if narrative_type:
        query = query.filter(models.AINarrative.narrative_type == narrative_type)
    narratives = query.order_by(models.AINarrative.generated_at.desc()).limit(limit).all()
    return narratives


@router.post("/narratives/{narrative_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_narrative(
    narrative_id: UUID,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss (hide) a narrative banner."""
    from datetime import datetime
    narrative = db.query(models.AINarrative).filter(
        models.AINarrative.id == narrative_id,
        models.AINarrative.family_id == current_user.family_id,
    ).first()
    if not narrative:
        raise HTTPException(status_code=404, detail="Narrative not found.")
    narrative.dismissed_at = datetime.utcnow()
    db.commit()
