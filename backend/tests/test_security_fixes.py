"""
Tests for three production blockers identified in code review:
  I6 – cross-family account access (auth.check_account_access)
  I4 – atomic transfer soft-delete (crud.delete_transaction)
  C1 – negative new_balance via BalanceAdjustRequest (schemas)
"""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
import uuid

import pytest
from pydantic import ValidationError

from app import models, crud, auth, schemas
from app.database import Base, SessionLocal, engine
from app.financial_logic import FinancialEngine


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


# ─── seed helpers ────────────────────────────────────────────────────────────

def _make_family(db, name="Family A", currency="USD"):
    family = models.Family(
        id=uuid.uuid4(),
        name=name,
        base_currency=currency,
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(family)
    db.flush()
    return family


def _make_user(db, family, role=models.Role.MEMBER, email="user@test.com"):
    user = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Test",
        last_name="User",
        email=email,
        role=role,
        active=True,
        activated=True,
        password_required=False,
    )
    db.add(user)
    db.flush()
    return user


def _make_account(db, family, owner_type=models.OwnerType.SHARED,
                  acc_type=models.AccountType.BANK, name="Test Account"):
    account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name=name,
        type=acc_type,
        currency="USD",
        owner_type=owner_type,
        current_balance=Decimal("1000.00"),
    )
    db.add(account)
    db.flush()
    return account


def _make_transfer_pair(db, user, source_account, target_account, amount="200.00"):
    """Create a cross-linked source+target transaction pair (transfer)."""
    source_tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=source_account.id,
        created_by_user_id=user.id,
        type=models.TransactionType.TRANSFER,
        amount=Decimal(amount),
        currency="USD",
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal(amount),
        transaction_date=datetime.utcnow(),
        is_source_transaction=True,
    )
    target_tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=target_account.id,
        created_by_user_id=user.id,
        type=models.TransactionType.TRANSFER,
        amount=Decimal(amount),
        currency="USD",
        exchange_rate_to_base=Decimal("1.0"),
        amount_in_base_currency=Decimal(amount),
        transaction_date=datetime.utcnow(),
        is_source_transaction=False,
    )
    db.add(source_tx)
    db.flush()
    target_tx.linked_transaction_id = source_tx.id
    db.add(target_tx)
    db.flush()
    source_tx.linked_transaction_id = target_tx.id
    db.commit()
    return source_tx, target_tx


# ─── I6: cross-family access control ─────────────────────────────────────────

def test_check_account_access_blocks_admin_from_different_family(db_session):
    """An admin must not access accounts belonging to a different family."""
    fam_a = _make_family(db_session, "Family A")
    fam_b = _make_family(db_session, "Family B")
    admin_a = _make_user(db_session, fam_a, models.Role.ADMIN, "admin_a@test.com")
    account_b = _make_account(db_session, fam_b)
    db_session.commit()

    assert auth.check_account_access(admin_a, account_b) is False


def test_check_account_access_blocks_member_accessing_shared_account_in_other_family(db_session):
    """A member cannot access a SHARED account that belongs to a different family."""
    fam_a = _make_family(db_session, "Family A")
    fam_b = _make_family(db_session, "Family B")
    member_a = _make_user(db_session, fam_a, models.Role.MEMBER, "member_a@test.com")
    shared_b = _make_account(db_session, fam_b, owner_type=models.OwnerType.SHARED)
    db_session.commit()

    assert auth.check_account_access(member_a, shared_b) is False


def test_check_account_access_still_grants_admin_own_family_account(db_session):
    """Admin access within their own family is unaffected by the family_id guard."""
    fam = _make_family(db_session)
    admin = _make_user(db_session, fam, models.Role.ADMIN, "admin@test.com")
    account = _make_account(db_session, fam)
    db_session.commit()

    assert auth.check_account_access(admin, account) is True


def test_check_account_access_still_grants_member_own_family_shared_account(db_session):
    """Member can still access SHARED accounts within their own family."""
    fam = _make_family(db_session)
    member = _make_user(db_session, fam, models.Role.MEMBER, "member@test.com")
    shared = _make_account(db_session, fam, owner_type=models.OwnerType.SHARED)
    db_session.commit()

    assert auth.check_account_access(member, shared) is True


# ─── I4: atomic transfer soft-delete ─────────────────────────────────────────

def test_delete_transfer_soft_deletes_both_legs(db_session):
    """Deleting the source leg of a transfer must soft-delete the target leg too."""
    fam = _make_family(db_session)
    admin = _make_user(db_session, fam, models.Role.ADMIN, "admin@test.com")
    src_acc = _make_account(db_session, fam, name="Source")
    tgt_acc = _make_account(db_session, fam, name="Target")
    source_tx, target_tx = _make_transfer_pair(db_session, admin, src_acc, tgt_acc)

    crud.delete_transaction(db_session, source_tx.id, admin)

    raw_source = db_session.query(models.Transaction).filter(
        models.Transaction.id == source_tx.id
    ).first()
    raw_target = db_session.query(models.Transaction).filter(
        models.Transaction.id == target_tx.id
    ).first()

    assert raw_source.deleted_at is not None, "Source leg not soft-deleted"
    assert raw_target.deleted_at is not None, "Target leg must be soft-deleted atomically"


def test_delete_transfer_target_deleted_even_if_balance_update_fails(db_session):
    """Both transfer legs must be committed deleted BEFORE any balance update runs.

    If the balance update raises (simulating a mid-operation crash), the target
    leg must already be committed as soft-deleted — not left active (phantom money).
    """
    fam = _make_family(db_session)
    admin = _make_user(db_session, fam, models.Role.ADMIN, "admin@test.com")
    src_acc = _make_account(db_session, fam, name="Source")
    tgt_acc = _make_account(db_session, fam, name="Target")
    source_tx, target_tx = _make_transfer_pair(db_session, admin, src_acc, tgt_acc)

    call_count = [0]
    original = FinancialEngine.update_account_balance

    def fail_on_first_call(db, account_id):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Simulated crash during balance update")
        return original(db, account_id)

    with patch.object(FinancialEngine, "update_account_balance", fail_on_first_call):
        try:
            crud.delete_transaction(db_session, source_tx.id, admin)
        except RuntimeError:
            pass

    raw_target = db_session.query(models.Transaction).filter(
        models.Transaction.id == target_tx.id
    ).first()
    assert raw_target.deleted_at is not None, (
        "Target leg still active after simulated crash — "
        "both legs must be committed before balance updates run"
    )


# ─── C1: negative new_balance rejected by schema ──────────────────────────────

def test_balance_adjust_request_rejects_negative_value():
    """BalanceAdjustRequest must reject a negative new_balance."""
    with pytest.raises(ValidationError):
        schemas.BalanceAdjustRequest(new_balance=Decimal("-500"))


def test_balance_adjust_request_rejects_minus_one():
    """BalanceAdjustRequest rejects -1 (boundary check)."""
    with pytest.raises(ValidationError):
        schemas.BalanceAdjustRequest(new_balance=Decimal("-1"))


def test_balance_adjust_request_accepts_zero():
    """BalanceAdjustRequest accepts 0 (clearing a balance is valid)."""
    req = schemas.BalanceAdjustRequest(new_balance=Decimal("0"))
    assert req.new_balance == Decimal("0")


def test_balance_adjust_request_accepts_positive():
    """BalanceAdjustRequest accepts a positive value."""
    req = schemas.BalanceAdjustRequest(new_balance=Decimal("1500.00"))
    assert req.new_balance == Decimal("1500.00")
