"""
G5: build_period_summary() must return formatted currency strings and include base_currency.

Verifies:
- All amount fields are strings formatted as "1,234.56 CCY"
- base_currency key is present and matches family.base_currency
- top_categories amounts are also formatted strings
- Returns None when there are no income/expense transactions
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

import pytest

from app import models
from app.database import Base, SessionLocal, engine
from app.services.ai_service import build_period_summary


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        db.query(models.Transaction).delete()
        db.query(models.Category).delete()
        db.query(models.Account).delete()
        db.query(models.User).delete()
        db.query(models.Family).delete()
        db.commit()
        yield db
    finally:
        db.rollback()
        db.query(models.Transaction).delete()
        db.query(models.Category).delete()
        db.query(models.Account).delete()
        db.query(models.User).delete()
        db.query(models.Family).delete()
        db.commit()
        db.close()


def _make_family(db, base_currency="USD"):
    fam = models.Family(
        id=uuid.uuid4(), name="Test Family", base_currency=base_currency,
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(fam)
    db.flush()
    return fam


def _make_user(db, family):
    user = models.User(
        id=uuid.uuid4(), family_id=family.id,
        first_name="Test", last_name="User",
        email=f"u_{uuid.uuid4().hex[:6]}@test.com",
        role=models.Role.ADMIN, active=True, activated=True,
        password_required=False,
    )
    db.add(user)
    db.flush()
    return user


def _make_account(db, family, currency="USD"):
    acc = models.Account(
        id=uuid.uuid4(), family_id=family.id, name="Main",
        type=models.AccountType.BANK, currency=currency,
        owner_type=models.OwnerType.SHARED,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        include_in_family_overview=True,
    )
    db.add(acc)
    db.flush()
    return acc


def _make_category(db, family, name, cat_type=models.CategoryType.EXPENSE):
    cat = models.Category(
        id=uuid.uuid4(), family_id=family.id, name=name, type=cat_type,
    )
    db.add(cat)
    db.flush()
    return cat


def _make_tx(db, user, account, tx_type, amount_base, category=None, tx_date=None):
    tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=account.id,
        created_by_user_id=user.id,
        type=tx_type,
        amount=Decimal(str(amount_base)),
        currency=account.currency,
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal(str(amount_base)),
        category_id=category.id if category else None,
        transaction_date=tx_date or datetime(2026, 5, 15),
    )
    db.add(tx)
    db.flush()
    return tx


START = date(2026, 5, 1)
END = date(2026, 5, 31)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_returns_none_when_no_transactions(db_session):
    fam = _make_family(db_session)
    result = build_period_summary(db_session, fam, START, END)
    assert result is None


def test_returns_none_when_only_transfers(db_session):
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    _make_tx(db_session, user, acc, models.TransactionType.TRANSFER, 500)
    db_session.commit()
    result = build_period_summary(db_session, fam, START, END)
    assert result is None


def test_base_currency_present_in_result(db_session):
    fam = _make_family(db_session, base_currency="GBP")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam, currency="GBP")
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 1000)
    db_session.commit()

    result = build_period_summary(db_session, fam, START, END)
    assert result is not None
    assert result["base_currency"] == "GBP"


def test_amounts_are_formatted_strings(db_session):
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 5000)
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 3500)
    db_session.commit()

    result = build_period_summary(db_session, fam, START, END)
    assert result is not None

    # All amount fields must be strings, not numbers
    assert isinstance(result["total_income"], str), "total_income should be a formatted string"
    assert isinstance(result["total_expenses"], str), "total_expenses should be a formatted string"
    assert isinstance(result["net_savings"], str), "net_savings should be a formatted string"
    assert isinstance(result["savings_rate"], str), "savings_rate should be a formatted string"


def test_amounts_contain_currency_symbol(db_session):
    fam = _make_family(db_session, base_currency="AED")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam, currency="AED")
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 10000)
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 6000)
    db_session.commit()

    result = build_period_summary(db_session, fam, START, END)
    assert result is not None
    assert "AED" in result["total_income"], f"Expected 'AED' in total_income: {result['total_income']}"
    assert "AED" in result["total_expenses"], f"Expected 'AED' in total_expenses: {result['total_expenses']}"
    assert "AED" in result["net_savings"], f"Expected 'AED' in net_savings: {result['net_savings']}"


def test_top_categories_amounts_are_formatted(db_session):
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    groceries = _make_category(db_session, fam, "Groceries")
    dining = _make_category(db_session, fam, "Dining")
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 5000)
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 800, category=groceries)
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 300, category=dining)
    db_session.commit()

    result = build_period_summary(db_session, fam, START, END)
    assert result is not None
    assert len(result["top_categories"]) == 2

    for cat in result["top_categories"]:
        assert isinstance(cat["amount"], str), f"Category amount should be string, got {type(cat['amount'])}"
        assert "USD" in cat["amount"], f"Expected 'USD' in category amount: {cat['amount']}"


def test_savings_rate_contains_percent(db_session):
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 10000)
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 7500)
    db_session.commit()

    result = build_period_summary(db_session, fam, START, END)
    assert result is not None
    assert "%" in result["savings_rate"], f"savings_rate should include '%': {result['savings_rate']}"
    assert "25.0%" == result["savings_rate"], f"Expected '25.0%', got {result['savings_rate']}"


def test_out_of_range_transactions_excluded(db_session):
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    # In range
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 5000, tx_date=datetime(2026, 5, 10))
    # Out of range
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 9999, tx_date=datetime(2026, 4, 30))
    db_session.commit()

    result = build_period_summary(db_session, fam, START, END)
    assert result is not None
    assert "5,000.00 USD" in result["total_income"], (
        f"Only the in-range 5000 should be counted. Got: {result['total_income']}"
    )
