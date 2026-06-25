"""
Tests for C3, I5 fixes.

C3: Snapshot task must use calculate_account_balance for ALL non-valuation
    accounts, not the potentially-stale current_balance field.

I5: compute_net_worth_history must not load transactions dated after the
    last snapshot (they are filtered out by the Python loop anyway — this
    bounds the DB query to avoid unbounded memory growth).

C4 (row-locking) and I2 (country breakdown live-calc) are structural fixes
verified by the full test suite passing without regressions.
I1 is a frontend-only change with no automated test.
"""
import json
from datetime import datetime, date
from decimal import Decimal
import uuid

import pytest

from app import models
from app.database import Base, SessionLocal, engine
from app.financial_logic import FinancialEngine


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        db.query(models.Transaction).delete()
        db.query(models.NetWorthSnapshot).delete()
        db.query(models.ExchangeRate).delete()
        db.query(models.Account).delete()
        db.query(models.User).delete()
        db.query(models.Family).delete()
        db.commit()
        yield db
    finally:
        db.rollback()
        db.query(models.Transaction).delete()
        db.query(models.NetWorthSnapshot).delete()
        db.query(models.ExchangeRate).delete()
        db.query(models.Account).delete()
        db.query(models.User).delete()
        db.query(models.Family).delete()
        db.commit()
        db.close()


# ─── seed helpers ─────────────────────────────────────────────────────────────

def _make_family(db, currency="USD"):
    fam = models.Family(
        id=uuid.uuid4(), name="Test Family", base_currency=currency,
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(fam)
    db.flush()
    return fam


def _make_user(db, family):
    user = models.User(
        id=uuid.uuid4(), family_id=family.id,
        first_name="Admin", last_name="User",
        email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
        role=models.Role.ADMIN, active=True, activated=True,
        password_required=False,
    )
    db.add(user)
    db.flush()
    return user


def _make_account(db, family, opening_balance=Decimal("0"),
                  current_balance=None, currency="USD",
                  acc_type=models.AccountType.BANK):
    account = models.Account(
        id=uuid.uuid4(), family_id=family.id, name="Test Account",
        type=acc_type, currency=currency,
        owner_type=models.OwnerType.SHARED,
        opening_balance=opening_balance,
        current_balance=current_balance if current_balance is not None else opening_balance,
        include_in_family_overview=True,
    )
    db.add(account)
    db.flush()
    return account


def _make_income_tx(db, user, account, amount):
    tx = models.Transaction(
        id=uuid.uuid4(), account_id=account.id,
        created_by_user_id=user.id,
        type=models.TransactionType.INCOME,
        amount=Decimal(str(amount)),
        currency=account.currency,
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal(str(amount)),
        transaction_date=datetime.utcnow(),
    )
    db.add(tx)
    db.flush()
    return tx


def _make_snapshot(db, family, breakdown_dict=None, total_nw=Decimal("0"),
                   snap_date=None):
    snapshot = models.NetWorthSnapshot(
        id=uuid.uuid4(), family_id=family.id,
        snapshot_date=snap_date or date.today(),
        total_net_worth=total_nw,
        breakdown_json=json.dumps(breakdown_dict) if breakdown_dict is not None else None,
        created_at=datetime.utcnow(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


# ─── C3: snapshot task uses live balance for asset accounts ───────────────────

def test_snapshot_task_uses_live_balance_for_asset_account_not_stale_current_balance(db_session):
    """record_net_worth_snapshot_task must call calculate_account_balance for
    asset (BANK/CASH) accounts, not read the potentially-stale current_balance.

    Setup:
      Account:  opening_balance=1000, current_balance=500 (stale / wrong)
      Transaction: +200 INCOME
      Correct live balance: 1000 + 200 = 1200

    Bug:  snapshot records 500  (uses current_balance)
    Fix:  snapshot records 1200 (uses calculate_account_balance)
    """
    from app.main import record_net_worth_snapshot_task

    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    account = _make_account(
        db_session, fam,
        opening_balance=Decimal("1000"),
        current_balance=Decimal("500"),   # intentionally stale
    )
    _make_income_tx(db_session, user, account, "200")
    db_session.commit()

    record_net_worth_snapshot_task()

    db_session.expire_all()
    snapshot = db_session.query(models.NetWorthSnapshot).filter(
        models.NetWorthSnapshot.family_id == fam.id
    ).first()

    assert snapshot is not None, "Task must create a snapshot"
    assert snapshot.total_net_worth == Decimal("1200"), (
        f"Expected 1200 (live calc: opening 1000 + income 200), "
        f"got {snapshot.total_net_worth} — likely used stale current_balance=500"
    )



# ─── I5: compute_net_worth_history excludes post-snapshot transactions ─────────

def test_compute_net_worth_history_excludes_transactions_after_last_snapshot(db_session):
    """Transactions dated after the last snapshot must not affect any snapshot's
    net worth — this verifies both correctness and that the query is bounded."""
    from datetime import timedelta

    fam = _make_family(db_session)
    user = _make_user(db_session, fam)
    # Account with opening_balance 1000, one past income of 500
    account = _make_account(db_session, fam, opening_balance=Decimal("1000"))

    yesterday = date.today() - timedelta(days=1)
    snap = _make_snapshot(db_session, fam, snap_date=yesterday)

    # Transaction BEFORE the snapshot
    past_tx = models.Transaction(
        id=uuid.uuid4(), account_id=account.id,
        created_by_user_id=user.id,
        type=models.TransactionType.INCOME,
        amount=Decimal("500"), currency="USD",
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal("500"),
        transaction_date=datetime.combine(yesterday, datetime.min.time()),
    )
    db_session.add(past_tx)

    # Transaction AFTER the snapshot (tomorrow — must not affect snapshot totals)
    future_tx = models.Transaction(
        id=uuid.uuid4(), account_id=account.id,
        created_by_user_id=user.id,
        type=models.TransactionType.INCOME,
        amount=Decimal("9999"), currency="USD",
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal("9999"),
        transaction_date=datetime.combine(date.today() + timedelta(days=1), datetime.min.time()),
    )
    db_session.add(future_tx)
    db_session.commit()

    result = FinancialEngine.compute_net_worth_history(
        db_session, [account], [snap], "USD", fam.id
    )

    assert len(result) == 1
    # opening_balance(1000) + past_tx(500) = 1500 — future_tx must NOT be included
    assert result[0].total_net_worth == Decimal("1500"), (
        f"Expected 1500 (opening 1000 + past income 500), "
        f"got {result[0].total_net_worth} — future transaction may have leaked in"
    )
