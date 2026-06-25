"""
G6: _compute_progress must convert linked account balance to goal currency
when they differ, and must populate base-currency equivalents.

Scenarios:
1. Goal in USD linked to GBP account → balance converted GBP→USD for progress
2. Goal in GBP linked to GBP account → no conversion (same currency)
3. base_currency/current_amount_in_base/target_amount_in_base always populated
4. Manual-contribution goal (no linked account) still gets base fields
"""
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app import models
from app.database import Base, SessionLocal, engine
from app.routers.goals import _compute_progress
from app.financial_logic import FinancialEngine


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        db.query(models.GoalContribution).delete()
        db.query(models.Goal).delete()
        db.query(models.Transaction).delete()
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


def _make_account(db, family, currency, opening_balance=Decimal("0")):
    acc = models.Account(
        id=uuid.uuid4(), family_id=family.id, name=f"{currency} Account",
        type=models.AccountType.BANK, currency=currency,
        owner_type=models.OwnerType.SHARED,
        opening_balance=opening_balance,
        current_balance=opening_balance,
        include_in_family_overview=True,
    )
    db.add(acc)
    db.flush()
    return acc


def _add_income(db, user, account, amount, exchange_rate_to_base=Decimal("1.0"), amount_in_base=None):
    tx = models.Transaction(
        id=uuid.uuid4(), account_id=account.id,
        created_by_user_id=user.id,
        type=models.TransactionType.INCOME,
        amount=Decimal(str(amount)),
        currency=account.currency,
        exchange_rate_to_base=exchange_rate_to_base,
        amount_in_base_currency=Decimal(str(amount_in_base or amount)),
        transaction_date=datetime.utcnow(),
    )
    db.add(tx)
    db.flush()
    return tx


def _make_goal(db, family, account=None, goal_currency="USD", target=10000,
               goal_type=models.GoalType.SAVINGS_TARGET, current_amount=None):
    goal = models.Goal(
        id=uuid.uuid4(), family_id=family.id,
        name="Test Goal", type=goal_type,
        target_amount=Decimal(str(target)),
        current_amount=Decimal(str(current_amount or 0)),
        currency=goal_currency,
        linked_account_id=account.id if account else None,
    )
    db.add(goal)
    db.flush()
    return goal


# ── Cross-currency linked account ──────────────────────────────────────────────

def test_linked_account_balance_converted_to_goal_currency(db_session):
    """
    Family base = USD. Account currency = GBP. Goal currency = USD.
    Account has 1000 GBP income → balance = 1000 GBP.
    DEFAULT_RATES: 1 GBP = 1.28 USD → progress should be 1280 USD.
    """
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    gbp_account = _make_account(db_session, fam, "GBP")
    goal = _make_goal(db_session, fam, account=gbp_account, goal_currency="USD", target=5000)
    _add_income(db_session, user, gbp_account, 1000, exchange_rate_to_base=Decimal("1.28"), amount_in_base=1280)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    gbp_to_usd = FinancialEngine.DEFAULT_RATES["GBP"] / FinancialEngine.DEFAULT_RATES["USD"]
    expected = Decimal("1000") * gbp_to_usd
    assert abs(progress.current_amount - expected) < Decimal("0.01"), (
        f"Expected ~{expected} USD, got {progress.current_amount}. "
        "Account balance (GBP) must be converted to goal currency (USD)."
    )


def test_same_currency_goal_and_account_no_conversion(db_session):
    """
    Account and goal both in GBP — no conversion should occur.
    Balance of 2000 GBP → progress 2000 GBP exactly.
    """
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    gbp_account = _make_account(db_session, fam, "GBP")
    goal = _make_goal(db_session, fam, account=gbp_account, goal_currency="GBP", target=5000)
    _add_income(db_session, user, gbp_account, 2000, exchange_rate_to_base=Decimal("1.28"), amount_in_base=2560)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.current_amount == Decimal("2000"), (
        f"Same-currency goal: balance should be used directly. Got {progress.current_amount}"
    )


# ── Base-currency equivalents ──────────────────────────────────────────────────

def test_base_currency_fields_populated_for_linked_goal(db_session):
    """base_currency, current_amount_in_base, target_amount_in_base must all be set."""
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam, "USD")
    goal = _make_goal(db_session, fam, account=acc, goal_currency="USD", target=10000)
    _add_income(db_session, user, acc, 3000)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.base_currency == "USD"
    assert progress.current_amount_in_base is not None
    assert progress.target_amount_in_base is not None
    assert progress.current_amount_in_base == Decimal("3000")
    assert progress.target_amount_in_base == Decimal("10000")


def test_base_currency_fields_converted_when_goal_in_foreign_currency(db_session):
    """
    Goal is in GBP, family base is USD.
    target_amount_in_base and current_amount_in_base must be in USD.
    """
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    acc = _make_account(db_session, fam, "GBP")
    # Goal in GBP: save 5000 GBP
    goal = _make_goal(db_session, fam, account=acc, goal_currency="GBP", target=5000)
    _add_income(db_session, user, acc, 2000, exchange_rate_to_base=Decimal("1.28"), amount_in_base=2560)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.base_currency == "USD"
    gbp_to_usd = FinancialEngine.DEFAULT_RATES["GBP"] / FinancialEngine.DEFAULT_RATES["USD"]
    expected_target_in_base = Decimal("5000") * gbp_to_usd
    expected_current_in_base = Decimal("2000") * gbp_to_usd
    assert abs(progress.target_amount_in_base - expected_target_in_base) < Decimal("0.01"), (
        f"target_amount_in_base: expected ~{expected_target_in_base}, got {progress.target_amount_in_base}"
    )
    assert abs(progress.current_amount_in_base - expected_current_in_base) < Decimal("0.01"), (
        f"current_amount_in_base: expected ~{expected_current_in_base}, got {progress.current_amount_in_base}"
    )


def test_manual_contribution_goal_gets_base_fields(db_session):
    """
    No linked account — manual contributions. Base-currency fields still computed.
    Goal in AED, family base USD.
    """
    fam = _make_family(db_session, base_currency="USD")
    # No linked account, manual contributions only
    goal = _make_goal(db_session, fam, account=None, goal_currency="AED",
                      target=10000, current_amount=2720)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.base_currency == "USD"
    assert progress.current_amount == Decimal("2720")
    assert progress.current_amount_in_base is not None
    assert progress.target_amount_in_base is not None

    aed_to_usd = FinancialEngine.DEFAULT_RATES["AED"] / FinancialEngine.DEFAULT_RATES["USD"]
    expected_current = Decimal("2720") * aed_to_usd
    assert abs(progress.current_amount_in_base - expected_current) < Decimal("0.01"), (
        f"Manual goal in AED: current_amount_in_base expected ~{expected_current}, "
        f"got {progress.current_amount_in_base}"
    )


def test_percent_uses_goal_currency_not_base(db_session):
    """
    Percent progress must be computed in goal currency after conversion, not base.
    Account in GBP with 2500 GBP saved. Goal in USD at 5000 USD.
    GBP→USD rate ~1.28: current_in_goal_currency = 2500 * 1.28 = 3200 USD.
    Progress = 3200/5000 = 64%.
    """
    fam = _make_family(db_session, base_currency="USD")
    user = _make_user(db_session, fam)
    gbp_account = _make_account(db_session, fam, "GBP")
    goal = _make_goal(db_session, fam, account=gbp_account, goal_currency="USD", target=5000)
    _add_income(db_session, user, gbp_account, 2500, exchange_rate_to_base=Decimal("1.28"), amount_in_base=3200)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    gbp_to_usd = FinancialEngine.DEFAULT_RATES["GBP"] / FinancialEngine.DEFAULT_RATES["USD"]
    current_usd = Decimal("2500") * gbp_to_usd
    expected_percent = float(current_usd / Decimal("5000") * 100)
    assert abs(progress.percent - expected_percent) < 0.5, (
        f"Expected percent ~{expected_percent:.1f}%, got {progress.percent}%"
    )
