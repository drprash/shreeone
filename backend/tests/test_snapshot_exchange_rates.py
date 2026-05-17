"""
Tests for C2: historical exchange rates embedded in net worth snapshots.

Bug: compute_net_worth_history builds ONE rate_cache before the snapshot loop
using today's rates, so all historical net worth figures are denominated at
today's exchange rate — producing false trends for multi-currency families.

Fix (Option B): embed the rates used at snapshot time into breakdown_json
so compute_net_worth_history can read them per-snapshot, falling back to
today's rate only for pre-fix snapshots.
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
    family = models.Family(
        id=uuid.uuid4(), name="Test Family", base_currency=currency,
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(family)
    db.flush()
    return family


def _make_account(db, family, currency="USD", opening_balance=Decimal("0"),
                  acc_type=models.AccountType.BANK):
    account = models.Account(
        id=uuid.uuid4(), family_id=family.id, name="Test Account",
        type=acc_type, currency=currency,
        owner_type=models.OwnerType.SHARED,
        opening_balance=opening_balance,
        current_balance=opening_balance,
        include_in_family_overview=True,
    )
    db.add(account)
    db.flush()
    return account


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


def _insert_rate(db, family, from_currency, to_currency, rate,
                 valid_date=None):
    """Insert an ExchangeRate row directly (bypassing service to control values)."""
    row = models.ExchangeRate(
        id=uuid.uuid4(), family_id=family.id,
        from_currency=from_currency, to_currency=to_currency,
        rate=Decimal(str(rate)),
        source=models.ExchangeRateSource.AUTO_FETCHED,
        valid_date=valid_date or date.today(),
        fetched_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


# ─── compute_net_worth_history: per-snapshot embedded rates ───────────────────

def test_compute_net_worth_history_uses_embedded_snapshot_rate(db_session):
    """When a snapshot has rates in breakdown_json, compute_net_worth_history
    must use those rates — not today's current rate — for that snapshot.

    Setup:
      Account: 1,000 INR
      Current DB rate:   INR→USD = 0.015  →  current value = 15.00 USD
      Embedded snapshot rate: INR→USD = 0.012  →  historical value = 12.00 USD

    Bug: returns 15.00 (uses today's rate for all snapshots)
    Fix: returns 12.00 (uses embedded rate from breakdown_json)
    """
    fam = _make_family(db_session, currency="USD")
    account = _make_account(db_session, fam, currency="INR",
                            opening_balance=Decimal("1000"))

    # Today's "current" rate stored in DB — distinct from historical rate
    _insert_rate(db_session, fam, "INR", "USD", Decimal("0.015"))

    # Snapshot with the historical rate embedded (0.012, used the day it was created)
    snapshot = _make_snapshot(db_session, fam, breakdown_dict={
        "cash": 0.0, "bank": 12.0, "investment": 0.0,
        "liability": 0.0,
        "rates": {"INR": "0.012"},
    }, total_nw=Decimal("12.00"))
    db_session.commit()

    result = FinancialEngine.compute_net_worth_history(
        db_session, [account], [snapshot], "USD", fam.id
    )

    assert len(result) == 1
    assert result[0].total_net_worth == Decimal("12.00"), (
        f"Expected 12.00 (embedded rate 0.012 × 1000 INR), "
        f"got {result[0].total_net_worth} — likely used current rate 0.015 → 15.00"
    )


def test_compute_net_worth_history_falls_back_to_current_rate_for_pre_fix_snapshots(db_session):
    """Snapshots created before this fix have no 'rates' in breakdown_json.
    compute_net_worth_history must fall back to today's rate gracefully —
    same behaviour as before the fix (no regression)."""
    fam = _make_family(db_session, currency="USD")
    account = _make_account(db_session, fam, currency="INR",
                            opening_balance=Decimal("1000"))

    # Current DB rate: 0.015
    _insert_rate(db_session, fam, "INR", "USD", Decimal("0.015"))

    # Old-style snapshot: breakdown_json has no "rates" key
    snapshot = _make_snapshot(db_session, fam, breakdown_dict={
        "cash": 0.0, "bank": 15.0, "investment": 0.0,
        "liability": 0.0,
    }, total_nw=Decimal("15.00"))
    db_session.commit()

    result = FinancialEngine.compute_net_worth_history(
        db_session, [account], [snapshot], "USD", fam.id
    )

    assert len(result) == 1
    # Falls back to current DB rate 0.015 → 1000 × 0.015 = 15.00
    assert result[0].total_net_worth == Decimal("15.00")


def test_compute_net_worth_history_uses_correct_rate_per_snapshot_independently(db_session):
    """Each snapshot uses its own embedded rate — different snapshots can have
    different rates for the same currency pair."""
    fam = _make_family(db_session, currency="USD")
    account = _make_account(db_session, fam, currency="INR",
                            opening_balance=Decimal("1000"))

    from datetime import timedelta
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Current DB rate 0.015 (fallback for snapshots without embedded rates)
    _insert_rate(db_session, fam, "INR", "USD", Decimal("0.015"))

    # Two snapshots with different embedded rates
    snap_old = _make_snapshot(db_session, fam, breakdown_dict={
        "rates": {"INR": "0.010"},
    }, total_nw=Decimal("10.00"), snap_date=yesterday)

    snap_new = _make_snapshot(db_session, fam, breakdown_dict={
        "rates": {"INR": "0.012"},
    }, total_nw=Decimal("12.00"), snap_date=today)
    db_session.commit()

    result = FinancialEngine.compute_net_worth_history(
        db_session, [account], [snap_old, snap_new], "USD", fam.id
    )

    assert len(result) == 2
    totals = {r.snapshot_date: r.total_net_worth for r in result}
    assert totals[yesterday] == Decimal("10.00"), (
        f"Old snapshot: expected 10.00 (rate 0.010), got {totals[yesterday]}"
    )
    assert totals[today] == Decimal("12.00"), (
        f"New snapshot: expected 12.00 (rate 0.012), got {totals[today]}"
    )


# ─── snapshot task: embeds rates in breakdown_json ────────────────────────────

def test_snapshot_task_embeds_exchange_rates_in_breakdown_json(db_session):
    """record_net_worth_snapshot_task must store the rates it fetched inside
    breakdown_json so future calls to compute_net_worth_history can use them."""
    from app.main import record_net_worth_snapshot_task

    fam = _make_family(db_session, currency="USD")
    # INR account — forces a rate lookup during snapshot creation
    _make_account(db_session, fam, currency="INR", opening_balance=Decimal("1000"))

    # Insert a predictable rate so the task uses a known value
    _insert_rate(db_session, fam, "INR", "USD", Decimal("0.013"))
    db_session.commit()

    # Run the scheduler task (uses its own internal DB session)
    record_net_worth_snapshot_task()

    # Re-read snapshot created by the task
    db_session.expire_all()
    snapshot = db_session.query(models.NetWorthSnapshot).filter(
        models.NetWorthSnapshot.family_id == fam.id
    ).first()

    assert snapshot is not None, "Task must create a NetWorthSnapshot"
    assert snapshot.breakdown_json is not None, "breakdown_json must not be None"

    bd = json.loads(snapshot.breakdown_json)
    assert "rates" in bd, (
        f"breakdown_json must contain a 'rates' key. Got keys: {list(bd.keys())}"
    )
    assert "INR" in bd["rates"], (
        f"'rates' must include INR since the family has an INR account. "
        f"Got: {bd['rates']}"
    )
    assert Decimal(str(bd["rates"]["INR"])) == Decimal("0.013"), (
        f"Embedded rate must match the rate used at snapshot time (0.013). "
        f"Got: {bd['rates']['INR']}"
    )


def test_snapshot_task_omits_rates_key_for_single_currency_family(db_session):
    """For families where all accounts use the base currency, no rate conversion
    is needed — breakdown_json['rates'] should be an empty dict (or absent)."""
    from app.main import record_net_worth_snapshot_task

    fam = _make_family(db_session, currency="USD")
    # All accounts in USD — no conversion needed
    _make_account(db_session, fam, currency="USD", opening_balance=Decimal("500"))
    db_session.commit()

    record_net_worth_snapshot_task()

    db_session.expire_all()
    snapshot = db_session.query(models.NetWorthSnapshot).filter(
        models.NetWorthSnapshot.family_id == fam.id
    ).first()

    assert snapshot is not None
    bd = json.loads(snapshot.breakdown_json)
    # rates key must exist but be empty — no foreign-currency accounts
    rates = bd.get("rates", {})
    assert rates == {}, f"Single-currency family must have empty rates dict, got {rates}"
