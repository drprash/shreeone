from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.database import get_db
from app import models, schemas
import bcrypt

# THIS WAS MISSING - Add it back
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    try:
        # Ensure both are bytes
        if isinstance(plain_password, str):
            plain_password = plain_password.encode('utf-8')
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        
        # Bcrypt has 72 byte limit
        if len(plain_password) > 72:
            plain_password = plain_password[:72]
            
        return bcrypt.checkpw(plain_password, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Generate a hash from a password."""
    # Convert to bytes
    password_bytes = password.encode('utf-8') if isinstance(password, str) else password
    
    # Bcrypt has 72 byte limit
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt, expire

def create_refresh_token(data: dict, jti: str) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.setdefault("v", 0)
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None or payload.get("type") != "access":
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.active == True,
        models.User.deleted_at.is_(None)
    ).first()
    
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != models.Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def check_account_access(user: models.User, account: models.Account) -> bool:
    """Check if user can access an account"""
    if user.role == models.Role.ADMIN:
        return True
    if account.owner_type == models.OwnerType.SHARED:
        return True
    if account.owner_user_id == user.id:
        return True
    return False

def check_transaction_access(user: models.User, transaction: models.Transaction) -> bool:
    """Check if user can view/modify a transaction"""
    if user.role == models.Role.ADMIN:
        return True
    if transaction.created_by_user_id == user.id:
        return True
    return check_account_access(user, transaction.account)
def require_member_permission(permission_name: str):
    """
    Create a dependency that checks member-level permissions.
    
    Usage:
        @router.post("/transactions")
        def create_transaction(
            ...,
            current_user: models.User = Depends(require_member_permission("add_transaction"))
        ):
    """
    async def check_permission(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> models.User:
        # Admins always have all permissions
        if current_user.role == models.Role.ADMIN:
            return current_user
        
        # Get member permissions
        perm = db.query(models.MemberPermission).filter(
            models.MemberPermission.family_id == current_user.family_id,
            models.MemberPermission.user_id == current_user.id
        ).first()
        
        if not perm:
            # Member doesn't have explicit permissions - deny by default for restricted actions
            if permission_name in ["add_account", "delete_account", "manage_categories"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission_name}"
                )
            # Default allow for basic actions
            return current_user
        
        # Check specific permission
        permission_field = f"can_{permission_name}"
        has_permission = getattr(perm, permission_field, False)
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_name}"
            )
        
        return current_user
    
    return check_permission