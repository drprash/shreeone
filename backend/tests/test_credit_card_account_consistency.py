from datetime import datetime
from decimal import Decimal
import uuid

import pytest

from app import models, crud
from app.database import Base, SessionLocal, engine


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        db.query(models.Transaction).delete()
        db.query(models.Account).delete()
        db.query(models.User).delete()
        db.query(models.Family).delete()
        db.commit()
        yield db
    finally:
        db.rollback()
        db.query(models.Transaction).delete()
        db.query(models.Account).delete()
        db.query(models.User).delete()
        db.query(models.Family).delete()
        db.commit()
        db.close()


def _seed_family_admin_and_credit(db):
    family = models.Family(
        id=uuid.uuid4(),
        name="Consistency Family",
        base_currency="USD",
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(family)

    admin = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Admin",
        last_name="User",
        email=f"consistency-admin-{uuid.uuid4()}@example.com",
        role=models.Role.ADMIN,
        active=True,
        activated=True,
        password_required=False,
    )
    db.add(admin)

    credit_account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Credit Card",
        type=models.AccountType.CREDIT_CARD,
        currency="USD",
        owner_type=models.OwnerType.SHARED,
        opening_balance=Decimal("0"),
        current_balance=Decimal("-999.99"),  # intentionally stale/incorrect
        include_in_family_overview=True,
    )
    db.add(credit_account)
    db.commit()

    tx_date = datetime.utcnow().replace(day=5, hour=12, minute=0, second=0, microsecond=0)
    expense_tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=credit_account.id,
        created_by_user_id=admin.id,
        type=models.TransactionType.EXPENSE,
        amount=Decimal("120.00"),
        currency="USD",
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal("120.00"),
        transaction_date=tx_date,
        is_source_transaction=True,
    )
    db.add(expense_tx)
    db.commit()

    return family, admin, credit_account


def test_list_accounts_recalculates_credit_card_balance(db_session):
    family, admin, credit_account = _seed_family_admin_and_credit(db_session)

    accounts = crud.get_family_accounts(db_session, family.id, admin)
    listed = next(a for a in accounts if a.id == credit_account.id)

    assert listed.current_balance == Decimal("120.00")


def test_get_account_matches_listed_credit_card_balance(db_session):
    family, admin, credit_account = _seed_family_admin_and_credit(db_session)

    listed_accounts = crud.get_family_accounts(db_session, family.id, admin)
    listed = next(a for a in listed_accounts if a.id == credit_account.id)

    detailed = crud.get_account(db_session, credit_account.id)

    assert detailed is not None
    assert listed.current_balance == Decimal("120.00")
    assert detailed.current_balance == Decimal("120.00")
    assert detailed.current_balance == listed.current_balance
