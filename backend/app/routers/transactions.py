from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app import schemas, models, crud, auth
from app.database import get_db
from app.financial_logic import FinancialEngine

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.post("/", response_model=schemas.TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Verify account access
    account = crud.get_account(db, transaction.account_id)
    if not account or not auth.check_account_access(current_user, account):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found or access denied"
        )

    normalized_currency = (transaction.currency or account.currency or current_user.family.base_currency or "USD").upper()
    transaction = transaction.model_copy(update={"currency": normalized_currency})
    
    # For transfers, verify target account too
    if transaction.type == models.TransactionType.TRANSFER and transaction.target_account_id:
        target_account = crud.get_account(db, transaction.target_account_id)
        if not target_account or not auth.check_account_access(current_user, target_account):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target account not found or access denied"
            )
        
        # Ensure same family
        if target_account.family_id != current_user.family_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot transfer to external family account"
            )
    
    try:
        transaction_obj, linked_obj = FinancialEngine.process_transaction(db, current_user, transaction)
        
        # Audit log
        crud.create_audit_log(
            db=db,
            user_id=current_user.id,
            action="CREATE",
            entity_type="Transaction",
            entity_id=transaction_obj.id,
            new_values=str(transaction.dict())
        )
        
        return transaction_obj
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=List[schemas.TransactionListResponse])
def list_family_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Get transactions for the user's family.
    
    Data visibility filtered based on family privacy level:
    - PRIVATE: User sees only their own transactions
    - SHARED: User sees shared account transactions + their own
    - FAMILY: User sees all family transactions
    - Admin: Always sees all transactions
    """
    transactions = crud.get_family_transactions(
        db=db,
        family_id=current_user.family_id,
        user=current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        transaction_type=type
    )
    return transactions

@router.get("/account/{account_id}", response_model=List[schemas.TransactionListResponse])
def list_account_transactions(
    account_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    account = crud.get_account(db, account_id)
    if not account or not auth.check_account_access(current_user, account):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found or access denied"
        )
    
    transactions = crud.get_account_transactions(
        db, account_id, skip, limit, start_date, end_date, transaction_type=type
    )
    return transactions

@router.get("/{transaction_id}", response_model=schemas.TransactionListResponse)
def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    transaction = crud.get_transaction(db, transaction_id)
    if not transaction or not auth.check_transaction_access(current_user, transaction):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    return transaction

@router.put("/{transaction_id}", response_model=schemas.TransactionResponse)
def update_transaction(
    transaction_id: UUID,
    transaction_update: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        updated = crud.update_transaction(db, transaction_id, transaction_update, current_user)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        crud.create_audit_log(
            db=db,
            user_id=current_user.id,
            action="UPDATE",
            entity_type="Transaction",
            entity_id=transaction_id,
            new_values=str(transaction_update.dict(exclude_unset=True))
        )
        
        return updated
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        if not crud.delete_transaction(db, transaction_id, current_user):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        crud.create_audit_log(
            db=db,
            user_id=current_user.id,
            action="DELETE",
            entity_type="Transaction",
            entity_id=transaction_id
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
