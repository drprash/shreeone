from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from app import schemas, models, crud, auth
from app.database import get_db

router = APIRouter(prefix="/accounts", tags=["Accounts"])

@router.put("/reorder", status_code=200)
def reorder_accounts(
    items: List[schemas.AccountReorderItem],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    crud.reorder_accounts(db, current_user.family_id, items)
    return {"status": "ok"}

@router.post("/", response_model=schemas.AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    account: schemas.AccountCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Validate owner permissions
    if account.owner_type == models.OwnerType.PERSONAL:
        if account.owner_user_id and account.owner_user_id != current_user.id:
            # Only admin can create personal accounts for others
            if current_user.role != models.Role.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot create personal account for another user"
                )
        if not account.owner_user_id:
            account.owner_user_id = current_user.id
    
    # Only admin can create shared accounts
    if account.owner_type == models.OwnerType.SHARED and current_user.role != models.Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can create shared accounts"
        )
    
    db_account = crud.create_account(db, account, current_user.family_id)
    
    # Create audit log
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CREATE",
        entity_type="Account",
        entity_id=db_account.id,
        new_values=str(account.dict())
    )
    
    return db_account

@router.get("/", response_model=List[schemas.AccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    accounts = crud.get_family_accounts(db, current_user.family_id, current_user)
    return accounts

@router.get("/{account_id}", response_model=schemas.AccountResponse)
def get_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    account = crud.get_account(db, account_id)
    if not account or not auth.check_account_access(current_user, account):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    return account

@router.put("/{account_id}", response_model=schemas.AccountResponse)
def update_account(
    account_id: UUID,
    account_update: schemas.AccountUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    account = crud.get_account(db, account_id)
    if not account or not auth.check_account_access(current_user, account):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    # Only admin can update shared accounts or accounts not owned by them
    if current_user.role != models.Role.ADMIN:
        if account.owner_type == models.OwnerType.SHARED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify shared account"
            )
        if account.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify another user's account"
            )
    
    old_values = str(account.__dict__)
    updated_account = crud.update_account(db, account_id, account_update)
    
    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="UPDATE",
        entity_type="Account",
        entity_id=account_id,
        old_values=old_values,
        new_values=str(account_update.dict(exclude_unset=True))
    )
    
    return updated_account

@router.post("/{account_id}/adjust-balance", response_model=schemas.AccountResponse)
def adjust_account_balance(
    account_id: UUID,
    adjust: schemas.BalanceAdjustRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    account = crud.get_account(db, account_id)
    if not account or not auth.check_account_access(current_user, account):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    if current_user.role != models.Role.ADMIN:
        if account.owner_type == models.OwnerType.SHARED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify shared account"
            )
        if account.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify another user's account"
            )

    current_balance = account.current_balance or Decimal('0')
    new_balance = adjust.new_balance
    difference = new_balance - current_balance

    if difference == 0:
        return account

    is_liability = account.type in models.LIABILITY_ACCOUNT_TYPES

    if is_liability:
        # Liability sign convention is inverted: balance represents debt.
        # Reducing balance (paying off debt) requires an INCOME transaction.
        # Increasing balance (adding more debt) requires an EXPENSE transaction.
        if difference < 0:
            tx_type = models.TransactionType.INCOME
            category_type = models.CategoryType.INCOME
        else:
            tx_type = models.TransactionType.EXPENSE
            category_type = models.CategoryType.EXPENSE
    else:
        if difference > 0:
            tx_type = models.TransactionType.INCOME
            category_type = models.CategoryType.INCOME
        else:
            tx_type = models.TransactionType.EXPENSE
            category_type = models.CategoryType.EXPENSE

    category = crud.get_or_create_system_category(
        db, current_user.family_id, category_type, "Modified Balance"
    )

    from app.financial_logic import FinancialEngine
    base_currency = current_user.family.base_currency
    if account.currency == base_currency:
        exchange_rate = Decimal('1.0')
    else:
        exchange_rate = FinancialEngine.get_exchange_rate(
            db, account.currency, base_currency, family_id=current_user.family_id
        )

    amount = abs(difference)
    amount_in_base = amount * exchange_rate

    transaction = models.Transaction(
        account_id=account_id,
        created_by_user_id=current_user.id,
        type=tx_type,
        amount=amount,
        currency=account.currency,
        exchange_rate_to_base=exchange_rate,
        amount_in_base_currency=amount_in_base,
        category_id=category.id,
        description="Difference",
        transaction_date=datetime.utcnow(),
        is_source_transaction=True
    )
    db.add(transaction)
    db.commit()

    FinancialEngine.update_account_balance(db, str(account_id))

    crud.create_audit_log(
        db=db,
        user_id=current_user.id,
        action="ADJUST_BALANCE",
        entity_type="Account",
        entity_id=account_id,
        old_values=str(current_balance),
        new_values=str(new_balance)
    )

    db.refresh(account)
    return account

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    account = crud.get_account(db, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    # Check permissions: admin can delete any account, members can only delete their own personal accounts
    if current_user.role != models.Role.ADMIN:
        if account.owner_type != models.OwnerType.PERSONAL or account.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete this account"
            )
    
    try:
        if crud.delete_account(db, account_id):
            crud.create_audit_log(
                db=db,
                user_id=current_user.id,
                action="DELETE",
                entity_type="Account",
                entity_id=account_id
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
