"""Tests for account soft-delete with transaction-aware confirmation."""
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


def _seed(db):
    """Seed a family, admin user, and one shared bank account."""
    family = models.Family(
        id=uuid.uuid4(),
        name="Test Family",
        base_currency="USD",
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(family)

    admin = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Admin",
        last_name="User",
        email="admin@test.com",
        role=models.Role.ADMIN,
        active=True,
        activated=True,
        password_required=False,
    )
    db.add(admin)

    bank = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Test Bank",
        type=models.AccountType.BANK,
        currency="USD",
        owner_type=models.OwnerType.SHARED,
        current_balance=Decimal("1000.00"),
    )
    db.add(bank)
    db.commit()
    return family, admin, bank


def _make_transaction(db, admin, account):
    """Add one expense transaction to an account."""
    txn = models.Transaction(
        id=uuid.uuid4(),
        account_id=account.id,
        created_by_user_id=admin.id,
        type=models.TransactionType.EXPENSE,
        amount=Decimal("50.00"),
        currency="USD",
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal("50.00"),
        transaction_date=datetime.utcnow(),
    )
    db.add(txn)
    db.commit()
    return txn


def test_transaction_count_zero_for_new_account(db_session):
    family, admin, bank = _seed(db_session)
    accounts = crud.get_family_accounts(db_session, family.id, admin)
    target = next(a for a in accounts if a.id == bank.id)
    assert target.transaction_count == 0


def test_transaction_count_reflects_active_transactions(db_session):
    family, admin, bank = _seed(db_session)
    _make_transaction(db_session, admin, bank)
    _make_transaction(db_session, admin, bank)
    accounts = crud.get_family_accounts(db_session, family.id, admin)
    target = next(a for a in accounts if a.id == bank.id)
    assert target.transaction_count == 2


def test_transaction_count_excludes_soft_deleted_transactions(db_session):
    family, admin, bank = _seed(db_session)
    txn = _make_transaction(db_session, admin, bank)
    txn.deleted_at = datetime.utcnow()
    db_session.commit()
    accounts = crud.get_family_accounts(db_session, family.id, admin)
    target = next(a for a in accounts if a.id == bank.id)
    assert target.transaction_count == 0


def test_delete_account_with_transactions_succeeds(db_session):
    family, admin, bank = _seed(db_session)
    _make_transaction(db_session, admin, bank)
    result = crud.delete_account(db_session, bank.id)
    assert result is True
    assert crud.get_account(db_session, bank.id) is None


def test_delete_account_sets_deleted_at(db_session):
    family, admin, bank = _seed(db_session)
    crud.delete_account(db_session, bank.id)
    raw = db_session.query(models.Account).filter(
        models.Account.id == bank.id
    ).first()
    assert raw.deleted_at is not None


def test_get_account_including_archived_returns_deleted_account(db_session):
    family, admin, bank = _seed(db_session)
    crud.delete_account(db_session, bank.id)
    assert crud.get_account(db_session, bank.id) is None
    found = crud.get_account_including_archived(db_session, bank.id)
    assert found is not None
    assert found.id == bank.id
    assert found.deleted_at is not None


def test_get_account_including_archived_returns_active_account(db_session):
    family, admin, bank = _seed(db_session)
    found = crud.get_account_including_archived(db_session, bank.id)
    assert found is not None
    assert found.deleted_at is None


def test_transactions_still_accessible_after_account_archived(db_session):
    family, admin, bank = _seed(db_session)
    txn = _make_transaction(db_session, admin, bank)
    crud.delete_account(db_session, bank.id)

    # Normal get_account returns None for archived accounts
    assert crud.get_account(db_session, bank.id) is None

    # get_account_including_archived finds it (used by router's access check)
    found = crud.get_account_including_archived(db_session, bank.id)
    assert found is not None

    # Transactions are still queryable by account_id
    transactions = crud.get_account_transactions(db_session, bank.id, 0, 100)
    assert len(transactions) == 1
    assert transactions[0].id == txn.id
