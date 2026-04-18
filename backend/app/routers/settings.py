from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import date
from app import schemas, models, crud, auth
from app.database import get_db

router = APIRouter(prefix="/settings", tags=["Settings"])

# ============ Member Permission Endpoints ============

@router.get("/permissions", response_model=List[schemas.MemberPermissionResponse])
def get_member_permissions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Get all member permissions for the family"""
    permissions = crud.get_family_member_permissions(db, current_user.family_id)
    return permissions

@router.get("/permissions/{user_id}", response_model=schemas.MemberPermissionResponse)
def get_user_permission(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Get specific member permission"""
    permission = crud.get_member_permission(db, current_user.family_id, user_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member permission not found"
        )
    return permission

@router.post("/permissions", response_model=schemas.MemberPermissionResponse, status_code=status.HTTP_201_CREATED)
def set_member_permissions(
    permission: schemas.MemberPermissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Create or update member permissions"""
    # Verify user exists in family
    user = crud.get_user(db, permission.user_id)
    if not user or user.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in family"
        )
    
    db_permission = crud.create_member_permission(db, current_user.family_id, permission)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_PERMISSION",
        entity_type="MemberPermission",
        entity_id=db_permission.id,
        new_values=str(permission.dict())
    )
    
    return db_permission

@router.put("/permissions/{user_id}", response_model=schemas.MemberPermissionResponse)
def update_member_permissions(
    user_id: UUID,
    permission: schemas.MemberPermissionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Update specific member permissions"""
    db_permission = crud.update_member_permission(db, current_user.family_id, user_id, permission)
    if not db_permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member permission not found"
        )
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_PERMISSION",
        entity_type="MemberPermission",
        entity_id=db_permission.id,
        new_values=str(permission.dict())
    )
    
    return db_permission

# ============ Budget Setting Endpoints ============

@router.get("/budgets", response_model=List[schemas.BudgetWithCategoryResponse])
def get_family_budgets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get all budget settings for the family"""
    budgets = crud.get_family_budget_settings(db, current_user.family_id)
    return budgets

@router.get("/budgets/{budget_id}", response_model=schemas.BudgetWithCategoryResponse)
def get_budget(
    budget_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get specific budget setting"""
    budget = crud.get_budget_setting(db, budget_id)
    if not budget or budget.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    return budget

@router.post("/budgets", response_model=schemas.BudgetWithCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    budget: schemas.BudgetSettingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Create a new budget setting"""
    # Verify category and user if provided
    if budget.category_id:
        category = crud.get_category(db, budget.category_id)
        if not category or category.family_id != current_user.family_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
    
    if budget.user_id:
        user = crud.get_user(db, budget.user_id)
        if not user or user.family_id != current_user.family_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    
    db_budget = crud.create_budget_setting(db, current_user.family_id, budget)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CREATE_BUDGET",
        entity_type="BudgetSetting",
        entity_id=db_budget.id,
        new_values=str(budget.dict())
    )
    
    return db_budget

@router.put("/budgets/{budget_id}", response_model=schemas.BudgetWithCategoryResponse)
def update_budget(
    budget_id: UUID,
    budget: schemas.BudgetSettingUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Update a budget setting"""
    db_budget = crud.get_budget_setting(db, budget_id)
    if not db_budget or db_budget.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    db_budget = crud.update_budget_setting(db, budget_id, budget)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_BUDGET",
        entity_type="BudgetSetting",
        entity_id=db_budget.id,
        new_values=str(budget.dict())
    )
    
    return db_budget

@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Delete a budget setting"""
    db_budget = crud.get_budget_setting(db, budget_id)
    if not db_budget or db_budget.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    crud.delete_budget_setting(db, budget_id)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="DELETE_BUDGET",
        entity_type="BudgetSetting",
        entity_id=budget_id,
        new_values="DELETED"
    )

# ============ Recurring Payment Endpoints ============

@router.get("/recurring-payments", response_model=List[schemas.RecurringPaymentDetailResponse])
def get_family_recurring_payments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get all recurring payments for the family"""
    payments = crud.get_family_recurring_payments(db, current_user.family_id)
    return payments

@router.get("/recurring-payments/{payment_id}", response_model=schemas.RecurringPaymentDetailResponse)
def get_recurring_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get specific recurring payment"""
    payment = crud.get_recurring_payment(db, payment_id)
    if not payment or payment.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring payment not found"
        )
    return payment

@router.post("/recurring-payments", response_model=schemas.RecurringPaymentDetailResponse, status_code=status.HTTP_201_CREATED)
def create_recurring_payment(
    payment: schemas.RecurringPaymentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Create a new recurring payment"""
    # Verify account and category
    account = crud.get_account(db, payment.account_id)
    if not account or account.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    category = crud.get_category(db, payment.category_id)
    if not category or category.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    if payment.assigned_to_user_id:
        user = crud.get_user(db, payment.assigned_to_user_id)
        if not user or user.family_id != current_user.family_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned user not found"
            )
    
    db_payment = crud.create_recurring_payment(db, current_user.family_id, current_user.id, payment)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CREATE_RECURRING_PAYMENT",
        entity_type="RecurringPayment",
        entity_id=db_payment.id,
        new_values=str(payment.dict())
    )
    
    return db_payment

@router.put("/recurring-payments/{payment_id}", response_model=schemas.RecurringPaymentDetailResponse)
def update_recurring_payment(
    payment_id: UUID,
    payment: schemas.RecurringPaymentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Update a recurring payment"""
    db_payment = crud.get_recurring_payment(db, payment_id)
    if not db_payment or db_payment.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring payment not found"
        )
    
    # Only admin or assigned user can update
    if current_user.role != models.Role.ADMIN and db_payment.assigned_to_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this payment"
        )
    
    db_payment = crud.update_recurring_payment(db, payment_id, payment)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_RECURRING_PAYMENT",
        entity_type="RecurringPayment",
        entity_id=db_payment.id,
        new_values=str(payment.dict())
    )
    
    return db_payment
@router.delete("/recurring-payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_recurring_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Deactivate a recurring payment"""
    db_payment = crud.get_recurring_payment(db, payment_id)
    if not db_payment or db_payment.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurring payment not found"
        )
    
    crud.deactivate_recurring_payment(db, payment_id)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="DEACTIVATE_RECURRING_PAYMENT",
        entity_type="RecurringPayment",
        entity_id=payment_id
    )

# ============ Family Preference Endpoints ============

@router.get("/preferences", response_model=schemas.FamilyPreferenceResponse)
def get_family_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get family preferences"""
    preferences = crud.get_or_create_family_preference(db, current_user.family_id)
    return preferences

@router.put("/preferences", response_model=schemas.FamilyPreferenceResponse)
def update_family_preferences(
    preferences: schemas.FamilyPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Update family preferences"""
    db_preferences = crud.update_family_preference(db, current_user.family_id, preferences)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_PREFERENCE",
        entity_type="FamilyPreference",
        entity_id=db_preferences.id,
        new_values=str(preferences.dict())
    )
    
    return db_preferences

# ============ Family Profile Endpoints ============

@router.get("/family-profile", response_model=schemas.FamilyProfileResponse)
def get_family_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get family profile"""
    family = crud.get_family_profile(db, current_user.family_id)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found"
        )
    return family

@router.put("/family-profile", response_model=schemas.FamilyProfileResponse)
def update_family_profile(
    profile: schemas.FamilyProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Update family profile"""
    family = crud.update_family_profile(db, current_user.family_id, profile)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found"
        )
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_FAMILY_PROFILE",
        entity_type="Family",
        entity_id=family.id,
        new_values=str(profile.dict())
    )
    
    return family

# ============ Member Transfer Admin Role ============

@router.post("/transfer-admin-role")
def transfer_admin_role(
    request: schemas.TransferAdminRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Transfer admin role to another member"""
    if request.new_admin_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer role to yourself"
        )
    
    new_admin = crud.get_user(db, request.new_admin_user_id)
    if not new_admin or new_admin.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in family"
        )
    
    # Update roles
    current_user.role = models.Role.MEMBER
    new_admin.role = models.Role.ADMIN
    db.commit()
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="TRANSFER_ADMIN_ROLE",
        entity_type="User",
        entity_id=new_admin.id,
        new_values=f"Transferred admin role from {current_user.id} to {new_admin.id}"
    )
    
    return {
        "message": "Admin role transferred successfully",
        "new_admin": {"id": new_admin.id, "first_name": new_admin.first_name, "last_name": new_admin.last_name, "email": new_admin.email}
    }

# ============ Remove Family Member (deactivate) ============

@router.post("/remove-member/{user_id}")
def remove_family_member(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Deactivate a family member (admin only)"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from family"
        )
    
    user = crud.get_user(db, user_id)
    if not user or user.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in family"
        )
    
    if user.role == models.Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot remove admin member. Transfer role first."
        )
    
    user.active = False
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="REMOVE_MEMBER",
        entity_type="User",
        entity_id=user.id,
        new_values=f"Deactivated member {user.email}"
    )
    
    return {"message": "Member removed successfully", "user_id": user.id}

# ============ Currency Endpoints (Admin only) ============

@router.get("/currencies", response_model=List[schemas.FamilyCurrencyResponse])
def list_currencies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """List secondary currencies for the family, with current rate vs base."""
    from app.exchange_rate_service import get_stored_rate
    from app.financial_logic import FinancialEngine

    rows = (
        db.query(models.FamilyCurrency)
        .filter(models.FamilyCurrency.family_id == current_user.family_id)
        .order_by(models.FamilyCurrency.added_at)
        .all()
    )
    result = []
    base = current_user.family.base_currency
    for row in rows:
        rate = get_stored_rate(db, current_user.family_id, row.currency_code, base)
        if rate is None:
            rate = FinancialEngine.get_exchange_rate(db, row.currency_code, base)
        result.append(
            schemas.FamilyCurrencyResponse(
                id=row.id,
                family_id=row.family_id,
                currency_code=row.currency_code,
                added_at=row.added_at,
                current_rate=rate,
            )
        )
    return result


@router.post("/currencies", response_model=schemas.FamilyCurrencyResponse, status_code=status.HTTP_201_CREATED)
def add_currency(
    payload: schemas.FamilyCurrencyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Add a secondary currency (Admin only)."""
    code = payload.currency_code.upper()
    if code == current_user.family.base_currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add the base currency as a secondary currency",
        )
    existing = (
        db.query(models.FamilyCurrency)
        .filter(
            models.FamilyCurrency.family_id == current_user.family_id,
            models.FamilyCurrency.currency_code == code,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{code} is already a secondary currency",
        )
    row = models.FamilyCurrency(family_id=current_user.family_id, currency_code=code)
    db.add(row)
    db.commit()
    db.refresh(row)
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="ADD_SECONDARY_CURRENCY",
        entity_type="FamilyCurrency",
        entity_id=row.id,
        new_values=code,
    )
    return schemas.FamilyCurrencyResponse(
        id=row.id,
        family_id=row.family_id,
        currency_code=row.currency_code,
        added_at=row.added_at,
        current_rate=None,
    )


@router.delete("/currencies/{code}", status_code=status.HTTP_204_NO_CONTENT)
def remove_currency(
    code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Remove a secondary currency. Blocked if active accounts still use it."""
    code = code.upper()
    row = (
        db.query(models.FamilyCurrency)
        .filter(
            models.FamilyCurrency.family_id == current_user.family_id,
            models.FamilyCurrency.currency_code == code,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not found")

    # Block removal if any active account uses this currency
    conflicting = (
        db.query(models.Account)
        .filter(
            models.Account.family_id == current_user.family_id,
            models.Account.currency == code,
            models.Account.deleted_at.is_(None),
        )
        .first()
    )
    if conflicting:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot remove {code}: account '{conflicting.name}' still uses this currency",
        )
    db.delete(row)
    db.commit()
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="REMOVE_SECONDARY_CURRENCY",
        entity_type="FamilyCurrency",
        entity_id=row.id,
        new_values=code,
    )


# ============ Exchange Rate Endpoints ============

@router.get("/exchange-rates", response_model=List[schemas.ExchangeRateResponse])
def list_exchange_rates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """List most-recent stored rates for base↔secondary currency pairs."""
    from sqlalchemy import func

    secondary_codes = [
        fc.currency_code
        for fc in db.query(models.FamilyCurrency)
        .filter(models.FamilyCurrency.family_id == current_user.family_id)
        .all()
    ]
    if not secondary_codes:
        return []

    base = current_user.family.base_currency
    all_codes = list({base} | set(secondary_codes))

    # Get the latest valid_date per pair
    subq = (
        db.query(
            models.ExchangeRate.from_currency,
            models.ExchangeRate.to_currency,
            func.max(models.ExchangeRate.valid_date).label("max_date"),
        )
        .filter(
            models.ExchangeRate.family_id == current_user.family_id,
            models.ExchangeRate.from_currency.in_(all_codes),
            models.ExchangeRate.to_currency.in_(all_codes),
        )
        .group_by(models.ExchangeRate.from_currency, models.ExchangeRate.to_currency)
        .subquery()
    )

    rows = (
        db.query(models.ExchangeRate)
        .join(
            subq,
            (models.ExchangeRate.from_currency == subq.c.from_currency)
            & (models.ExchangeRate.to_currency == subq.c.to_currency)
            & (models.ExchangeRate.valid_date == subq.c.max_date),
        )
        .filter(models.ExchangeRate.family_id == current_user.family_id)
        .all()
    )
    return rows


@router.put("/exchange-rates", response_model=schemas.ExchangeRateResponse)
def set_exchange_rate(
    payload: schemas.ExchangeRateManualUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Manually set a rate for a currency pair on a specific date (Admin only)."""
    existing = (
        db.query(models.ExchangeRate)
        .filter(
            models.ExchangeRate.family_id == current_user.family_id,
            models.ExchangeRate.from_currency == payload.from_currency,
            models.ExchangeRate.to_currency == payload.to_currency,
            models.ExchangeRate.valid_date == payload.valid_date,
        )
        .first()
    )
    if existing:
        existing.rate = payload.rate
        existing.source = models.ExchangeRateSource.MANUAL
        existing.fetched_at = __import__("datetime").datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    row = models.ExchangeRate(
        family_id=current_user.family_id,
        from_currency=payload.from_currency,
        to_currency=payload.to_currency,
        rate=payload.rate,
        source=models.ExchangeRateSource.MANUAL,
        valid_date=payload.valid_date,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="SET_EXCHANGE_RATE",
        entity_type="ExchangeRate",
        entity_id=row.id,
        new_values=str(payload.dict()),
    )
    return row


@router.post("/exchange-rates/refresh", status_code=status.HTTP_200_OK)
def refresh_exchange_rates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin),
):
    """Trigger an on-demand ECB rate fetch for this family (Admin only)."""
    from app.exchange_rate_service import fetch_family_rates
    family = db.query(models.Family).filter(models.Family.id == current_user.family_id).first()
    count = fetch_family_rates(db, family)
    return {"message": f"Fetched and stored {count} rate pairs", "pairs_updated": count}


@router.post("/reactivate-member/{user_id}")
def reactivate_family_member(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Reactivate a family member (admin only)"""
    user = crud.get_user(db, user_id)
    if not user or user.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in family"
        )
    
    user.active = True
    db.commit()
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="REACTIVATE_MEMBER",
        entity_type="User",
        entity_id=user.id,
        new_values=f"Reactivated member {user.email}"
    )
    
    return {"message": "Member reactivated successfully", "user_id": user.id}
