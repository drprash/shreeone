from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app import auth, models
from app.database import get_db

router = APIRouter(prefix="/sync", tags=["sync"])


class PullAccount(BaseModel):
    id: str
    family_id: str
    name: str
    type: str
    currency: str
    owner_type: str
    owner_user_id: Optional[str]
    owner_name: Optional[str]
    include_in_family_overview: bool
    opening_balance: float
    sort_order: int
    created_at: datetime
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]


class PullCategory(BaseModel):
    id: str
    family_id: str
    name: str
    type: str
    color: Optional[str]
    icon: Optional[str]
    sort_order: int
    created_at: datetime
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]


class PullTransaction(BaseModel):
    id: str
    account_id: str
    category_id: Optional[str]
    type: str
    amount: float
    currency: str
    description: Optional[str]
    transaction_date: datetime
    linked_transaction_id: Optional[str]
    is_source_transaction: bool
    created_at: datetime
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]


class PullResponse(BaseModel):
    accounts: List[PullAccount]
    categories: List[PullCategory]
    transactions: List[PullTransaction]
    server_timestamp: datetime


@router.get("/pull", response_model=PullResponse)
def sync_pull(
    since: Optional[datetime] = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Returns all accounts, categories, and transactions (including soft-deleted)
    that were created or modified after `since`. Used by the PWA to catch up
    after a period of disconnection without re-fetching all data.
    """
    cursor = since or datetime.fromtimestamp(0)

    accounts = (
        db.query(models.Account)
        .options(joinedload(models.Account.owner))
        .filter(
            models.Account.family_id == current_user.family_id,
            or_(
                models.Account.created_at > cursor,
                models.Account.updated_at > cursor,
                models.Account.deleted_at > cursor,
                models.Account.updated_at.is_(None),
            ),
        )
        .order_by(models.Account.updated_at.asc(), models.Account.created_at.asc())
        .limit(limit)
        .all()
    )

    categories = (
        db.query(models.Category)
        .filter(
            models.Category.family_id == current_user.family_id,
            or_(
                models.Category.created_at > cursor,
                models.Category.updated_at > cursor,
                models.Category.deleted_at > cursor,
                models.Category.updated_at.is_(None),
            ),
        )
        .order_by(models.Category.updated_at.asc(), models.Category.created_at.asc())
        .limit(limit)
        .all()
    )

    transactions = (
        db.query(models.Transaction)
        .join(models.Account, models.Transaction.account_id == models.Account.id)
        .filter(
            models.Account.family_id == current_user.family_id,
            or_(
                models.Transaction.created_at > cursor,
                models.Transaction.updated_at > cursor,
                models.Transaction.deleted_at > cursor,
                models.Transaction.updated_at.is_(None),
            ),
        )
        .order_by(models.Transaction.updated_at.asc(), models.Transaction.created_at.asc())
        .limit(limit)
        .all()
    )

    return PullResponse(
        accounts=[
            PullAccount(
                id=str(item.id),
                family_id=str(item.family_id),
                name=item.name,
                type=item.type.value if hasattr(item.type, "value") else str(item.type),
                currency=item.currency,
                owner_type=item.owner_type.value if hasattr(item.owner_type, "value") else str(item.owner_type),
                owner_user_id=str(item.owner_user_id) if item.owner_user_id else None,
                owner_name=item.owner_name,
                include_in_family_overview=bool(item.include_in_family_overview),
                opening_balance=float(item.opening_balance or 0),
                sort_order=item.sort_order,
                created_at=item.created_at,
                updated_at=item.updated_at,
                deleted_at=item.deleted_at,
            )
            for item in accounts
        ],
        categories=[
            PullCategory(
                id=str(item.id),
                family_id=str(item.family_id),
                name=item.name,
                type=item.type.value if hasattr(item.type, "value") else str(item.type),
                color=item.color,
                icon=item.icon,
                sort_order=item.sort_order,
                created_at=item.created_at,
                updated_at=item.updated_at,
                deleted_at=item.deleted_at,
            )
            for item in categories
        ],
        transactions=[
            PullTransaction(
                id=str(item.id),
                account_id=str(item.account_id),
                category_id=str(item.category_id) if item.category_id else None,
                type=item.type.value if hasattr(item.type, "value") else str(item.type),
                amount=float(item.amount or 0),
                currency=item.currency,
                description=item.description,
                transaction_date=item.transaction_date,
                linked_transaction_id=str(item.linked_transaction_id) if item.linked_transaction_id else None,
                is_source_transaction=bool(item.is_source_transaction),
                created_at=item.created_at,
                updated_at=item.updated_at,
                deleted_at=item.deleted_at,
            )
            for item in transactions
        ],
        server_timestamp=datetime.utcnow(),
    )
