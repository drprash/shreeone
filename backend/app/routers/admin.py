from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app import schemas, models, crud, auth
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/members", response_model=schemas.MemberInviteInformation, status_code=status.HTTP_201_CREATED)
def create_family_member_with_activation(
    member_data: schemas.MemberCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """
    Create a new family member with activation token.
    The member will receive an activation token via response that you'll share manually.
    They'll use it to set their password on first login.
    """
    # Check if email already exists
    if crud.get_user_by_email(db, member_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create member with activation token
    user, activation_token = crud.create_member_with_activation_token(
        db=db,
        email=member_data.email,
        first_name=member_data.first_name,
        last_name=member_data.last_name,
        family_id=current_user.family_id,
        role=member_data.role,
        activation_token_hours=72
    )
    
    # Create default member permissions
    if user.role == models.Role.MEMBER:
        crud.create_member_permission(
            db=db,
            family_id=current_user.family_id,
            perm=schemas.MemberPermissionCreate(
                user_id=user.id,
                can_add_transaction=True,
                can_edit_transaction=True,
                can_delete_transaction=False,
                can_add_account=False,
                can_edit_account=False,
                can_delete_account=False,
                can_manage_categories=False,
                can_view_all_accounts=True,
                can_view_all_transactions=True,
            )
        )
    
    # Audit log
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CREATE_MEMBER",
        entity_type="User",
        entity_id=user.id,
        new_values=f"Created member {user.email} with role {user.role.value}"
    )
    
    return schemas.MemberInviteInformation(
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        activation_token=activation_token.token,
        activation_expires_at=activation_token.expires_at
    )

@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_family_member(
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    if crud.get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = crud.create_user(db, user_data, current_user.family_id, models.Role.MEMBER, activated=True, password_required=False)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CREATE_USER",
        entity_type="User",
        entity_id=user.id,
        new_values=f"Created user {user.email} with role MEMBER"
    )
    
    return user

@router.get("/users", response_model=List[schemas.UserResponse])
def list_all_family_members(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    return crud.get_family_users(db, current_user.family_id, current_user)

@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_family_member(
    user_id: UUID,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    if user_id == current_user.id and user_update.role and user_update.role != models.Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote yourself from admin"
        )
    
    user = crud.update_user(db, user_id, user_update)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_family_member(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    if not crud.delete_user(db, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

@router.post("/users/{user_id}/reset-password", response_model=schemas.PasswordResetTokenResponse)
def reset_member_password(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """
    Generate a password reset token for a family member.
    Admin can share this token with the member to reset their password.
    """
    # Verify user exists and belongs to same family
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot reset password for users outside your family"
        )
    
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reset password for inactive users"
        )

    # Invalidate existing refresh tokens before issuing reset flow
    crud.bump_user_token_version(db, user)
    
    # Generate password reset token
    reset_token = crud.create_activation_token(db, user.id, activation_token_hours=72)
    
    # Audit log
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="PASSWORD_RESET_GENERATED",
        entity_type="User",
        entity_id=user.id,
        new_values=f"Password reset token generated by admin for {user.email}"
    )
    
    return schemas.PasswordResetTokenResponse(
        token=reset_token.token,
        expires_at=reset_token.expires_at,
        user_email=user.email
    )

@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    logs = db.query(models.AuditLog).filter(
        models.AuditLog.user_id.in_(
            db.query(models.User.id).filter(models.User.family_id == current_user.family_id)
        )
    ).order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    
    return logs
