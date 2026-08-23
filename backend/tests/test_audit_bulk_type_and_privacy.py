"""
Remaining 2026-08 financial-audit fixes:

1. POST /transactions/bulk must honor the `type` field its schema already
   accepts (INCOME/EXPENSE) instead of hardcoding EXPENSE, and reject
   TRANSFER rows (transfers need linked legs, unsupported in bulk).
2. PRIVATE/SHARED privacy filtering must also match transactions on
   accounts the user OWNS, not only transactions they created — an
   admin-created transaction on a member's personal account was invisible
   to its owner in the family list but visible in account detail.
"""
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import models, crud, auth
from app.database import SessionLocal, Base, engine, get_db
from app.routers.transactions import router as transactions_router


def _wipe(db):
    for model in [
        models.AuditLog,
        models.Transaction,
        models.MemberPermission,
        models.ExchangeRate,
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


def _make_account(db, family, owner=None, currency="USD"):
    account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name=f"Acct-{uuid.uuid4().hex[:6]}",
        type=models.AccountType.BANK,
        currency=currency,
        owner_type=models.OwnerType.PERSONAL if owner else models.OwnerType.SHARED,
        owner_user_id=owner.id if owner else None,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
    )
    db.add(account)
    db.commit()
    return account


def _make_tx(db, account, user, amount, tx_type=models.TransactionType.EXPENSE):
    tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=account.id,
        created_by_user_id=user.id,
        type=tx_type,
        amount=Decimal(str(amount)),
        currency=account.currency,
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal(str(amount)),
        transaction_date=datetime.utcnow(),
        is_source_transaction=True,
    )
    db.add(tx)
    db.commit()
    return tx


def _client_for(db, user):
    app = FastAPI()
    app.include_router(transactions_router)
    app.dependency_overrides[auth.get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _bulk_item(account_id, tx_type, amount="50.00"):
    return {
        "type": tx_type,
        "amount": amount,
        "currency": "USD",
        "description": f"bulk {tx_type}",
        "transaction_date": "2026-08-01T00:00:00",
        "account_id": str(account_id),
    }


# ── 1. Bulk import honors transaction type ───────────────────────────────────

def test_bulk_import_honors_income_type(db_session):
    family, admin, _ = _make_family(db_session)
    account = _make_account(db_session, family)
    client = _client_for(db_session, admin)

    resp = client.post("/transactions/bulk", json={
        "transactions": [_bulk_item(account.id, "INCOME", "100.00")]
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["created"] == 1
    assert resp.json()["failed"] == 0

    tx = db_session.query(models.Transaction).filter(
        models.Transaction.account_id == account.id
    ).one()
    assert tx.type == models.TransactionType.INCOME
    db_session.refresh(account)
    assert account.current_balance == Decimal("100.00")


def test_bulk_import_still_defaults_to_expense(db_session):
    family, admin, _ = _make_family(db_session)
    account = _make_account(db_session, family)
    client = _client_for(db_session, admin)

    item = _bulk_item(account.id, "EXPENSE", "40.00")
    del item["type"]  # omitted → schema default EXPENSE
    resp = client.post("/transactions/bulk", json={"transactions": [item]})
    assert resp.status_code == 201, resp.text
    assert resp.json()["created"] == 1

    tx = db_session.query(models.Transaction).filter(
        models.Transaction.account_id == account.id
    ).one()
    assert tx.type == models.TransactionType.EXPENSE


def test_bulk_import_rejects_transfer_type(db_session):
    family, admin, _ = _make_family(db_session)
    account = _make_account(db_session, family)
    client = _client_for(db_session, admin)

    resp = client.post("/transactions/bulk", json={
        "transactions": [
            _bulk_item(account.id, "TRANSFER", "10.00"),
            _bulk_item(account.id, "INCOME", "20.00"),
        ]
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["failed"] == 1
    txs = db_session.query(models.Transaction).filter(
        models.Transaction.account_id == account.id
    ).all()
    assert len(txs) == 1
    assert txs[0].type == models.TransactionType.INCOME


# ── 2. Privacy filtering includes owned accounts ─────────────────────────────

def test_private_member_sees_admin_created_tx_on_own_account(db_session):
    family, admin, member = _make_family(db_session, models.PrivacyLevel.PRIVATE)
    member_account = _make_account(db_session, family, owner=member)
    tx = _make_tx(db_session, member_account, admin, "75.00")

    visible = crud.get_family_transactions(db_session, family.id, member)
    assert tx.id in {t.id for t in visible}, \
        "owner must see transactions on their own account even if admin-created"


def test_private_member_does_not_see_other_members_transactions(db_session):
    family, admin, member = _make_family(db_session, models.PrivacyLevel.PRIVATE)
    member2 = _make_user(db_session, family, models.Role.MEMBER)
    db_session.commit()
    member2_account = _make_account(db_session, family, owner=member2)
    tx = _make_tx(db_session, member2_account, member2, "30.00")

    visible = crud.get_family_transactions(db_session, family.id, member)
    assert tx.id not in {t.id for t in visible}


def test_shared_member_sees_admin_created_tx_on_own_account(db_session):
    family, admin, member = _make_family(db_session, models.PrivacyLevel.SHARED)
    member_account = _make_account(db_session, family, owner=member)
    tx = _make_tx(db_session, member_account, admin, "60.00")

    visible = crud.get_family_transactions(db_session, family.id, member)
    assert tx.id in {t.id for t in visible}


def test_sync_pull_private_includes_admin_created_tx_on_own_account(db_session):
    from app.routers.sync import sync_pull

    family, admin, member = _make_family(db_session, models.PrivacyLevel.PRIVATE)
    member_account = _make_account(db_session, family, owner=member)
    tx = _make_tx(db_session, member_account, admin, "85.00")

    result = sync_pull(since=None, limit=1000, db=db_session, current_user=member)
    assert str(tx.id) in {t.id for t in result.transactions}
