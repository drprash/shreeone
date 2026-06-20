"""
Tests for FinancialEngine.get_period_stats().

Verifies: income/expense totals, date range filtering, daily totals shape,
category breakdown, member spending, and zero-income edge case.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

import pytest

from app import models
from app.database import Base, SessionLocal, engine
from app.financial_logic import FinancialEngine


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        db.query(models.GoalContribution).delete()
        db.query(models.Goal).delete()
        db.query(models.Transaction).delete()
        db.query(models.Category).delete()
        db.query(models.Account).delete()
        db.query(models.User).delete()
        db.query(models.Family).delete()
        db.commit()
        yield db
    finally:
        db.rollback()
        db.query(models.GoalContribution).delete()
        db.query(models.Goal).delete()
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


def _make_category(db, family, name):
    cat = models.Category(
        id=uuid.uuid4(), family_id=family.id, name=name,
        type=models.CategoryType.EXPENSE, color="#94a3b8",
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


def test_income_and_expense_totals(db_session):
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 5000,
             tx_date=datetime(2026, 5, 10))
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 3000,
             tx_date=datetime(2026, 5, 20))
    db_session.commit()

    result = FinancialEngine.get_period_stats(
        db_session, str(fam.id), user, START, END
    )

    assert result['income'] == Decimal('5000')
    assert result['expenses'] == Decimal('3000')
    assert result['savings'] == Decimal('2000')
    assert result['savings_rate'] == 40.0


def test_transactions_outside_range_excluded(db_session):
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 1000,
             tx_date=datetime(2026, 5, 1))
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 9999,
             tx_date=datetime(2026, 4, 30, 23, 59, 59))
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 9999,
             tx_date=datetime(2026, 6, 1))
    db_session.commit()

    result = FinancialEngine.get_period_stats(
        db_session, str(fam.id), user, START, END
    )

    assert result['income'] == Decimal('1000'), \
        f"Expected only in-range 1000, got {result['income']}"


def test_daily_totals_has_one_entry_per_day(db_session):
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    _make_account(db_session, fam)
    db_session.commit()

    start = date(2026, 5, 1)
    end = date(2026, 5, 7)
    result = FinancialEngine.get_period_stats(
        db_session, str(fam.id), user, start, end
    )

    assert len(result['daily_totals']) == 7, \
        f"Expected 7 daily entries, got {len(result['daily_totals'])}"
    assert result['daily_totals'][0].date == start
    assert result['daily_totals'][-1].date == end


def test_category_breakdown_populated(db_session):
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    cat = _make_category(db_session, fam, "Groceries")
    _make_tx(db_session, user, acc, models.TransactionType.INCOME, 5000,
             tx_date=datetime(2026, 5, 10))
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 800,
             category=cat, tx_date=datetime(2026, 5, 15))
    db_session.commit()

    result = FinancialEngine.get_period_stats(
        db_session, str(fam.id), user, START, END
    )

    assert len(result['categories']) == 1
    assert result['categories'][0].category_name == "Groceries"
    assert result['categories'][0].total_amount == Decimal('800')
    assert result['categories'][0].percentage == 100.0


def test_zero_income_gives_zero_savings_rate(db_session):
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    _make_account(db_session, fam)
    db_session.commit()

    result = FinancialEngine.get_period_stats(
        db_session, str(fam.id), user, START, END
    )

    assert result['income'] == Decimal('0')
    assert result['savings_rate'] == 0.0


def test_member_spending_populated(db_session):
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam)
    _make_tx(db_session, user, acc, models.TransactionType.EXPENSE, 500,
             tx_date=datetime(2026, 5, 10))
    db_session.commit()

    result = FinancialEngine.get_period_stats(
        db_session, str(fam.id), user, START, END
    )

    assert len(result['member_spending']) == 1
    assert result['member_spending'][0].total_expense == Decimal('500')
    assert result['member_spending'][0].transaction_count == 1
