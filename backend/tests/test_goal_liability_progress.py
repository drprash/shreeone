"""
I8: _compute_progress must invert balance for liability-linked goals.

For a DEBT_PAYOFF goal linked to a CREDIT_CARD account:
  - calculate_account_balance returns outstanding debt (positive = owed)
  - Progress should be (target - current_balance): i.e. how much has been paid off
  - Bug: current code treats the raw balance as progress, so a $5000 debt
    against a $5000 target shows 100% complete on day 1.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

import pytest

from app import models
from app.database import Base, SessionLocal, engine
from app.routers.goals import _compute_progress


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


def _make_family(db):
    fam = models.Family(
        id=uuid.uuid4(), name="Test Family", base_currency="USD",
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(fam)
    db.flush()
    return fam


def _make_user(db, family):
    user = models.User(
        id=uuid.uuid4(), family_id=family.id,
        first_name="User", last_name="Test",
        email=f"u_{uuid.uuid4().hex[:6]}@test.com",
        role=models.Role.ADMIN, active=True, activated=True,
        password_required=False,
    )
    db.add(user)
    db.flush()
    return user


def _make_credit_card(db, family, opening_balance=Decimal("0")):
    account = models.Account(
        id=uuid.uuid4(), family_id=family.id, name="My CC",
        type=models.AccountType.CREDIT_CARD, currency="USD",
        owner_type=models.OwnerType.SHARED,
        opening_balance=opening_balance,
        current_balance=opening_balance,
        include_in_family_overview=True,
    )
    db.add(account)
    db.flush()
    return account


def _make_goal(db, family, account, target, goal_type=models.GoalType.DEBT_PAYOFF):
    goal = models.Goal(
        id=uuid.uuid4(), family_id=family.id,
        name="Pay off CC", type=goal_type,
        target_amount=Decimal(str(target)),
        current_amount=Decimal("0"),
        currency="USD",
        linked_account_id=account.id,
    )
    db.add(goal)
    db.flush()
    return goal


def _add_payment(db, user, account, amount):
    """INCOME on a credit card = payment (reduces debt)."""
    tx = models.Transaction(
        id=uuid.uuid4(), account_id=account.id,
        created_by_user_id=user.id,
        type=models.TransactionType.INCOME,
        amount=Decimal(str(amount)), currency="USD",
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal(str(amount)),
        transaction_date=datetime.utcnow(),
    )
    db.add(tx)
    db.flush()
    return tx


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_debt_payoff_goal_zero_progress_when_fully_owed(db_session):
    """Opening balance = target → debt just started, progress must be 0%."""
    fam = _make_family(db_session)
    _make_user(db_session, fam)
    cc = _make_credit_card(db_session, fam, opening_balance=Decimal("5000"))
    goal = _make_goal(db_session, fam, cc, target=5000)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.current_amount == Decimal("0"), (
        f"No payments made: progress should be 0, got {progress.current_amount}. "
        f"Bug: raw CC balance (5000) is being used as progress."
    )
    assert progress.percent == 0.0, f"Expected 0%, got {progress.percent}%"


def test_debt_payoff_goal_partial_progress_after_payment(db_session):
    """After paying $2000 of a $5000 debt, progress must be $2000 (40%)."""
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    cc = _make_credit_card(db_session, fam, opening_balance=Decimal("5000"))
    goal = _make_goal(db_session, fam, cc, target=5000)
    _add_payment(db_session, user, cc, "2000")
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.current_amount == Decimal("2000"), (
        f"$2000 paid off a $5000 debt (target - remaining = 5000 - 3000). Got {progress.current_amount}."
    )
    assert abs(progress.percent - 40.0) < 0.1, f"Expected 40%, got {progress.percent}%"


def test_debt_payoff_goal_100_percent_when_fully_paid(db_session):
    """After paying off the full $5000, progress must be 100%."""
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    cc = _make_credit_card(db_session, fam, opening_balance=Decimal("5000"))
    goal = _make_goal(db_session, fam, cc, target=5000)
    _add_payment(db_session, user, cc, "5000")
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.current_amount == Decimal("5000"), (
        f"Debt fully paid: progress should equal target (5000), got {progress.current_amount}"
    )
    assert progress.percent == 100.0, f"Expected 100%, got {progress.percent}%"


def test_savings_goal_linked_to_bank_account_unaffected(db_session):
    """SAVINGS_TARGET goals linked to a BANK account must still use raw balance."""
    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    bank = models.Account(
        id=uuid.uuid4(), family_id=fam.id, name="Savings",
        type=models.AccountType.BANK, currency="USD",
        owner_type=models.OwnerType.SHARED,
        opening_balance=Decimal("3000"),
        current_balance=Decimal("3000"),
        include_in_family_overview=True,
    )
    db_session.add(bank)
    db_session.flush()
    goal = models.Goal(
        id=uuid.uuid4(), family_id=fam.id,
        name="Emergency Fund", type=models.GoalType.SAVINGS_TARGET,
        target_amount=Decimal("10000"),
        current_amount=Decimal("0"),
        currency="USD",
        linked_account_id=bank.id,
    )
    db_session.add(goal)
    db_session.commit()

    progress = _compute_progress(db_session, goal)

    assert progress.current_amount == Decimal("3000"), (
        f"Bank savings goal: balance should be used directly. Got {progress.current_amount}"
    )
    assert abs(progress.percent - 30.0) < 0.1, f"Expected 30%, got {progress.percent}%"
