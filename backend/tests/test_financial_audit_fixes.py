"""
Tests for the 2026-08 financial-logic audit fixes:

1. Cross-family tenant isolation on transaction view/update/delete
2. /sync/pull respects privacy levels and account visibility
3. calculate_account_balance: no FX drift for same-currency transactions
   on non-base-currency accounts
4. Updating one leg of a transfer keeps the linked leg in sync
5. Budget spent amounts are computed from actual transactions
6. MemberPermission flags are enforced on transaction/account routes
7. Recurring payments use family stored rates and are dated on the due date
"""
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import models, schemas, crud, auth
from app.database import SessionLocal, Base, engine, get_db
from app.financial_logic import FinancialEngine
from app.recurring_processor import RecurringPaymentProcessor
from app.routers.sync import sync_pull


def _wipe(db):
    for model in [
        models.AuditLog,
        models.Transaction,
        models.RecurringPayment,
        models.BudgetSetting,
        models.MemberPermission,
        models.ExchangeRate,
        models.GoalContribution,
        models.Goal,
        models.NetWorthSnapshot,
        models.FamilyCurrency,
        models.FamilyPreference,
        models.Account,
        models.Category,
        models.ActivationToken,
        models.RefreshToken,
        models.User,
        models.Family,
    ]:
        db.query(model).delete()
    db.commit()


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        _wipe(db)
        yield db
    finally:
        db.rollback()
        _wipe(db)
        db.close()


def _make_family(db, privacy_level=models.PrivacyLevel.FAMILY, base_currency="USD"):
    family = models.Family(
        id=uuid.uuid4(),
        name=f"Family-{uuid.uuid4().hex[:6]}",
        base_currency=base_currency,
        privacy_level=privacy_level,
    )
    db.add(family)
    admin = _make_user(db, family, models.Role.ADMIN)
    member = _make_user(db, family, models.Role.MEMBER)
    db.commit()
    return family, admin, member


def _make_user(db, family, role):
    user = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Admin" if role == models.Role.ADMIN else "Member",
        last_name="User",
        email=f"{uuid.uuid4().hex}@example.com",
        role=role,
        active=True,
        activated=True,
        password_required=False,
    )
    db.add(user)
    return user


def _make_account(db, family, owner=None, currency="USD",
                  acc_type=models.AccountType.BANK, opening=Decimal("0")):
    account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name=f"Acct-{uuid.uuid4().hex[:6]}",
        type=acc_type,
        currency=currency,
        owner_type=models.OwnerType.PERSONAL if owner else models.OwnerType.SHARED,
        owner_user_id=owner.id if owner else None,
        opening_balance=opening,
        current_balance=opening,
    )
    db.add(account)
    db.commit()
    return account


def _make_tx(db, account, user, amount, currency, rate, tx_type=models.TransactionType.EXPENSE,
             tx_date=None, category_id=None):
    tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=account.id,
        created_by_user_id=user.id,
        type=tx_type,
        amount=Decimal(str(amount)),
        currency=currency,
        exchange_rate_to_base=Decimal(str(rate)),
        amount_in_base_currency=Decimal(str(amount)) * Decimal(str(rate)),
        transaction_date=tx_date or datetime.utcnow(),
        category_id=category_id,
        is_source_transaction=True,
    )
    db.add(tx)
    db.commit()
    return tx


def _store_rate(db, family, from_c, to_c, rate, valid=None):
    db.add(models.ExchangeRate(
        family_id=family.id,
        from_currency=from_c,
        to_currency=to_c,
        rate=Decimal(str(rate)),
        source=models.ExchangeRateSource.MANUAL,
        valid_date=valid or date.today(),
    ))
    db.commit()


# ── 1. Cross-family tenant isolation ─────────────────────────────────────────

def test_admin_of_other_family_cannot_view_transaction(db_session):
    family_a, admin_a, member_a = _make_family(db_session)
    family_b, admin_b, _ = _make_family(db_session)
    account_a = _make_account(db_session, family_a, owner=member_a)
    tx = _make_tx(db_session, account_a, member_a, 50, "USD", 1)

    assert auth.check_transaction_access(admin_b, tx) is False
    assert auth.check_transaction_access(admin_a, tx) is True


def test_admin_of_other_family_cannot_update_transaction(db_session):
    family_a, _, member_a = _make_family(db_session)
    family_b, admin_b, _ = _make_family(db_session)
    account_a = _make_account(db_session, family_a, owner=member_a)
    tx = _make_tx(db_session, account_a, member_a, 50, "USD", 1)

    update = schemas.TransactionUpdate(amount=Decimal("99"))
    result = crud.update_transaction(db_session, tx.id, update, admin_b)
    assert result is None
    db_session.refresh(tx)
    assert tx.amount == Decimal("50")


def test_admin_of_other_family_cannot_delete_transaction(db_session):
    family_a, _, member_a = _make_family(db_session)
    family_b, admin_b, _ = _make_family(db_session)
    account_a = _make_account(db_session, family_a, owner=member_a)
    tx = _make_tx(db_session, account_a, member_a, 50, "USD", 1)

    assert crud.delete_transaction(db_session, tx.id, admin_b) is False
    db_session.refresh(tx)
    assert tx.deleted_at is None


# ── 2. /sync/pull privacy filtering ──────────────────────────────────────────

def _sync_setup(db, privacy_level):
    family, admin, member1 = _make_family(db, privacy_level)
    member2 = _make_user(db, family, models.Role.MEMBER)
    db.commit()
    own_acct = _make_account(db, family, owner=member1)
    other_acct = _make_account(db, family, owner=member2)
    shared_acct = _make_account(db, family, owner=None)

    tx_own = _make_tx(db, own_acct, member1, 10, "USD", 1)
    tx_other = _make_tx(db, other_acct, member2, 20, "USD", 1)
    tx_shared = _make_tx(db, shared_acct, member2, 30, "USD", 1)
    return family, admin, member1, member2, own_acct, other_acct, shared_acct, tx_own, tx_other, tx_shared


def test_sync_pull_private_member_sees_only_own_transactions(db_session):
    (_, _, member1, _, own_acct, other_acct, shared_acct,
     tx_own, tx_other, tx_shared) = _sync_setup(db_session, models.PrivacyLevel.PRIVATE)

    result = sync_pull(since=None, limit=1000, db=db_session, current_user=member1)
    tx_ids = {t.id for t in result.transactions}
    assert str(tx_own.id) in tx_ids
    assert str(tx_other.id) not in tx_ids
    assert str(tx_shared.id) not in tx_ids


def test_sync_pull_shared_member_sees_shared_and_own(db_session):
    (_, _, member1, _, own_acct, other_acct, shared_acct,
     tx_own, tx_other, tx_shared) = _sync_setup(db_session, models.PrivacyLevel.SHARED)

    result = sync_pull(since=None, limit=1000, db=db_session, current_user=member1)
    tx_ids = {t.id for t in result.transactions}
    assert str(tx_own.id) in tx_ids
    assert str(tx_shared.id) in tx_ids
    assert str(tx_other.id) not in tx_ids


def test_sync_pull_member_never_sees_other_members_personal_accounts(db_session):
    (_, _, member1, _, own_acct, other_acct, shared_acct,
     *_ ) = _sync_setup(db_session, models.PrivacyLevel.FAMILY)

    result = sync_pull(since=None, limit=1000, db=db_session, current_user=member1)
    acct_ids = {a.id for a in result.accounts}
    assert str(own_acct.id) in acct_ids
    assert str(shared_acct.id) in acct_ids
    assert str(other_acct.id) not in acct_ids


def test_sync_pull_admin_sees_everything(db_session):
    (_, admin, _, _, own_acct, other_acct, shared_acct,
     tx_own, tx_other, tx_shared) = _sync_setup(db_session, models.PrivacyLevel.PRIVATE)

    result = sync_pull(since=None, limit=1000, db=db_session, current_user=admin)
    tx_ids = {t.id for t in result.transactions}
    assert {str(tx_own.id), str(tx_other.id), str(tx_shared.id)} <= tx_ids
    acct_ids = {a.id for a in result.accounts}
    assert {str(own_acct.id), str(other_acct.id), str(shared_acct.id)} <= acct_ids


# ── 3. No FX drift on account balances ───────────────────────────────────────

def test_same_currency_tx_on_foreign_account_no_fx_drift(db_session):
    """A 100 AED expense on an AED account must reduce the balance by exactly
    100 AED regardless of what today's AED/USD rate is."""
    family, admin, _ = _make_family(db_session, base_currency="USD")
    account = _make_account(db_session, family, owner=admin, currency="AED",
                            opening=Decimal("1000"))
    # Deliberately non-reciprocal stored rates that differ from the historical tx rate
    _store_rate(db_session, family, "AED", "USD", "0.28")
    _store_rate(db_session, family, "USD", "AED", "3.5")
    _make_tx(db_session, account, admin, 100, "AED", "0.25")  # historical rate 0.25

    balance = FinancialEngine.calculate_account_balance(db_session, str(account.id))
    assert balance == Decimal("900.00")


def test_cross_currency_tx_on_foreign_account_converted_via_base(db_session):
    """A USD expense on an AED account is converted base→AED at the current rate."""
    family, admin, _ = _make_family(db_session, base_currency="USD")
    account = _make_account(db_session, family, owner=admin, currency="AED",
                            opening=Decimal("1000"))
    _store_rate(db_session, family, "AED", "USD", "0.28")
    _store_rate(db_session, family, "USD", "AED", "3.5")
    _make_tx(db_session, account, admin, 100, "AED", "0.25")
    _make_tx(db_session, account, admin, 50, "USD", "1.0")  # 50 USD * 3.5 = 175 AED

    balance = FinancialEngine.calculate_account_balance(db_session, str(account.id))
    assert balance == Decimal("725.00")


# ── 4. Transfer legs stay in sync on update ──────────────────────────────────

def _make_transfer(db, family, admin, source, target, amount):
    tx_in = schemas.TransactionCreate(
        type=models.TransactionType.TRANSFER,
        amount=Decimal(str(amount)),
        currency=source.currency,
        account_id=source.id,
        target_account_id=target.id,
        transaction_date=datetime.utcnow(),
    )
    return FinancialEngine.process_transaction(db, admin, tx_in)


def test_update_transfer_amount_syncs_linked_leg(db_session):
    family, admin, _ = _make_family(db_session, base_currency="USD")
    source = _make_account(db_session, family, owner=admin, currency="USD",
                           opening=Decimal("1000"))
    target = _make_account(db_session, family, owner=admin, currency="EUR")
    _store_rate(db_session, family, "USD", "EUR", "0.9")
    _store_rate(db_session, family, "EUR", "USD", "1.1")

    src_leg, tgt_leg = _make_transfer(db_session, family, admin, source, target, 100)
    assert tgt_leg.amount == Decimal("90.00")

    update = schemas.TransactionUpdate(amount=Decimal("200"))
    crud.update_transaction(db_session, src_leg.id, update, admin)

    db_session.refresh(tgt_leg)
    db_session.refresh(src_leg)
    # Target leg scales by the same conversion ratio (90/100)
    assert tgt_leg.amount == Decimal("180.00")
    assert tgt_leg.amount_in_base_currency == Decimal("180.00") * Decimal("1.1")
    assert src_leg.amount_in_base_currency == Decimal("200.00")

    # Both account balances reflect the new amount
    db_session.refresh(source)
    db_session.refresh(target)
    assert source.current_balance == Decimal("800.00")
    assert target.current_balance == Decimal("180.00")


def test_update_transfer_date_syncs_linked_leg(db_session):
    family, admin, _ = _make_family(db_session, base_currency="USD")
    source = _make_account(db_session, family, owner=admin, currency="USD")
    target = _make_account(db_session, family, owner=admin, currency="USD")

    src_leg, tgt_leg = _make_transfer(db_session, family, admin, source, target, 100)
    new_date = datetime(2026, 1, 15, 12, 0, 0)
    update = schemas.TransactionUpdate(transaction_date=new_date)
    crud.update_transaction(db_session, src_leg.id, update, admin)

    db_session.refresh(tgt_leg)
    assert tgt_leg.transaction_date == new_date


# ── 5. Budget spent computation ──────────────────────────────────────────────

def test_budget_spent_sums_current_month_category_expenses(db_session):
    family, admin, member = _make_family(db_session)
    account = _make_account(db_session, family, owner=None)
    category = models.Category(
        id=uuid.uuid4(), family_id=family.id, name="Groceries",
        type=models.CategoryType.EXPENSE,
    )
    db_session.add(category)
    db_session.commit()

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _make_tx(db_session, account, admin, 100, "USD", 1, tx_date=now, category_id=category.id)
    _make_tx(db_session, account, member, 50, "USD", 1, tx_date=now, category_id=category.id)
    # Previous month — must be excluded
    _make_tx(db_session, account, admin, 70, "USD", 1,
             tx_date=month_start - timedelta(days=3), category_id=category.id)
    # Different category — must be excluded
    _make_tx(db_session, account, admin, 33, "USD", 1, tx_date=now)

    budget = models.BudgetSetting(
        id=uuid.uuid4(), family_id=family.id, category_id=category.id,
        limit_amount=Decimal("500"), period=models.BudgetPeriod.MONTHLY,
    )
    db_session.add(budget)
    db_session.commit()

    assert crud.compute_budget_spent(db_session, budget) == Decimal("150.00")


def test_budget_spent_user_scoped(db_session):
    family, admin, member = _make_family(db_session)
    account = _make_account(db_session, family, owner=None)
    now = datetime.utcnow()
    _make_tx(db_session, account, admin, 100, "USD", 1, tx_date=now)
    _make_tx(db_session, account, member, 40, "USD", 1, tx_date=now)

    budget = models.BudgetSetting(
        id=uuid.uuid4(), family_id=family.id, user_id=member.id,
        limit_amount=Decimal("500"), period=models.BudgetPeriod.MONTHLY,
    )
    db_session.add(budget)
    db_session.commit()

    assert crud.compute_budget_spent(db_session, budget) == Decimal("40.00")


# ── 6. Member permission enforcement ─────────────────────────────────────────

def _client_for(db, user, routers):
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    app.dependency_overrides[auth.get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_member_without_delete_permission_cannot_delete_transaction(db_session):
    from app.routers.transactions import router as tx_router
    family, _, member = _make_family(db_session)
    account = _make_account(db_session, family, owner=member)
    tx = _make_tx(db_session, account, member, 25, "USD", 1)
    db_session.add(models.MemberPermission(
        family_id=family.id, user_id=member.id,
        can_add_transaction=True, can_edit_transaction=True,
        can_delete_transaction=False,
    ))
    db_session.commit()

    client = _client_for(db_session, member, [tx_router])
    resp = client.delete(f"/transactions/{tx.id}")
    assert resp.status_code == 403
    db_session.refresh(tx)
    assert tx.deleted_at is None


def test_member_with_delete_permission_can_delete_transaction(db_session):
    from app.routers.transactions import router as tx_router
    family, _, member = _make_family(db_session)
    account = _make_account(db_session, family, owner=member)
    tx = _make_tx(db_session, account, member, 25, "USD", 1)
    db_session.add(models.MemberPermission(
        family_id=family.id, user_id=member.id,
        can_delete_transaction=True,
    ))
    db_session.commit()

    client = _client_for(db_session, member, [tx_router])
    resp = client.delete(f"/transactions/{tx.id}")
    assert resp.status_code == 204


def test_member_without_permission_cannot_create_account(db_session):
    from app.routers.accounts import router as acct_router
    family, _, member = _make_family(db_session)

    client = _client_for(db_session, member, [acct_router])
    resp = client.post("/accounts/", json={
        "name": "Sneaky account",
        "type": "BANK",
        "currency": "USD",
        "owner_type": "PERSONAL",
    })
    assert resp.status_code == 403


# ── 7. Recurring payments: family rates + due-date dating ────────────────────

def test_recurring_payment_uses_family_stored_rate_and_due_date(db_session):
    family, admin, _ = _make_family(db_session, base_currency="USD")
    account = _make_account(db_session, family, owner=admin, currency="AED")
    category = models.Category(
        id=uuid.uuid4(), family_id=family.id, name="Bills",
        type=models.CategoryType.EXPENSE,
    )
    db_session.add(category)
    db_session.commit()

    due = datetime.utcnow() - timedelta(days=1)
    _store_rate(db_session, family, "AED", "USD", "0.28", valid=due.date())

    payment = models.RecurringPayment(
        id=uuid.uuid4(), family_id=family.id, account_id=account.id,
        category_id=category.id, name="Rent", amount=Decimal("100"),
        pattern=models.RecurrencePattern.MONTHLY, next_due_date=due,
        created_by_user_id=admin.id,
    )
    db_session.add(payment)
    db_session.commit()

    tx = RecurringPaymentProcessor.process_due_recurring_payment(
        db_session, payment, account, admin
    )
    assert tx is not None
    assert tx.exchange_rate_to_base == Decimal("0.28")
    assert tx.amount_in_base_currency == Decimal("28.00")
    assert tx.transaction_date == due
