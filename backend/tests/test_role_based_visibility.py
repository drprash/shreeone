from datetime import datetime
from decimal import Decimal
import uuid

import pytest

from app import models
from app.crud import get_family_transactions
from app.database import SessionLocal, Base, engine


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


def _create_family_and_users(db, privacy_level):
    family = models.Family(
        id=uuid.uuid4(),
        name=f"Family-{privacy_level.value}",
        base_currency="USD",
        privacy_level=privacy_level,
    )
    db.add(family)

    admin = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Admin",
        last_name="User",
        email=f"admin-{uuid.uuid4()}@example.com",
        role=models.Role.ADMIN,
        active=True,
        activated=True,
        password_required=False,
    )
    member_1 = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Member",
        last_name="One",
        email=f"member1-{uuid.uuid4()}@example.com",
        role=models.Role.MEMBER,
        active=True,
        activated=True,
        password_required=False,
    )
    member_2 = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Member",
        last_name="Two",
        email=f"member2-{uuid.uuid4()}@example.com",
        role=models.Role.MEMBER,
        active=True,
        activated=True,
        password_required=False,
    )
    db.add_all([admin, member_1, member_2])
    db.commit()

    return family, admin, member_1, member_2


def _create_accounts_and_transactions(db, family, member_1, member_2):
    shared_account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Shared Account",
        type=models.AccountType.BANK,
        currency="USD",
        owner_type=models.OwnerType.SHARED,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        include_in_family_overview=True,
    )
    member_1_account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Member1 Personal",
        type=models.AccountType.BANK,
        currency="USD",
        owner_type=models.OwnerType.PERSONAL,
        owner_user_id=member_1.id,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        include_in_family_overview=True,
    )
    member_2_account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Member2 Personal",
        type=models.AccountType.BANK,
        currency="USD",
        owner_type=models.OwnerType.PERSONAL,
        owner_user_id=member_2.id,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        include_in_family_overview=True,
    )
    db.add_all([shared_account, member_1_account, member_2_account])
    db.commit()

    tx_shared_member2 = models.Transaction(
        id=uuid.uuid4(),
        account_id=shared_account.id,
        created_by_user_id=member_2.id,
        type=models.TransactionType.EXPENSE,
        amount=Decimal("10.00"),
        currency="USD",
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal("10.00"),
        transaction_date=datetime.utcnow(),
        is_source_transaction=True,
        description="shared-by-member2",
    )
    tx_member1_personal = models.Transaction(
        id=uuid.uuid4(),
        account_id=member_1_account.id,
        created_by_user_id=member_1.id,
        type=models.TransactionType.EXPENSE,
        amount=Decimal("20.00"),
        currency="USD",
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal("20.00"),
        transaction_date=datetime.utcnow(),
        is_source_transaction=True,
        description="personal-member1",
    )
    tx_member2_personal = models.Transaction(
        id=uuid.uuid4(),
        account_id=member_2_account.id,
        created_by_user_id=member_2.id,
        type=models.TransactionType.EXPENSE,
        amount=Decimal("30.00"),
        currency="USD",
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal("30.00"),
        transaction_date=datetime.utcnow(),
        is_source_transaction=True,
        description="personal-member2",
    )

    db.add_all([tx_shared_member2, tx_member1_personal, tx_member2_personal])
    db.commit()


class TestRoleBasedVisibility:
    def test_private_mode_member_sees_only_own_transactions(self, db_session):
        family, _, member_1, member_2 = _create_family_and_users(
            db_session,
            models.PrivacyLevel.PRIVATE,
        )
        _create_accounts_and_transactions(db_session, family, member_1, member_2)

        rows = get_family_transactions(db_session, family.id, member_1, skip=0, limit=100)

        assert len(rows) == 1
        assert rows[0].created_by_user_id == member_1.id
        assert rows[0].description == "personal-member1"

    def test_shared_mode_member_sees_shared_and_own(self, db_session):
        family, _, member_1, member_2 = _create_family_and_users(
            db_session,
            models.PrivacyLevel.SHARED,
        )
        _create_accounts_and_transactions(db_session, family, member_1, member_2)

        rows = get_family_transactions(db_session, family.id, member_1, skip=0, limit=100)

        descriptions = {row.description for row in rows}
        assert "personal-member1" in descriptions
        assert "shared-by-member2" in descriptions
        assert "personal-member2" not in descriptions

    def test_family_mode_member_sees_all_family_transactions(self, db_session):
        family, _, member_1, member_2 = _create_family_and_users(
            db_session,
            models.PrivacyLevel.FAMILY,
        )
        _create_accounts_and_transactions(db_session, family, member_1, member_2)

        rows = get_family_transactions(db_session, family.id, member_1, skip=0, limit=100)

        descriptions = {row.description for row in rows}
        assert descriptions == {
            "personal-member1",
            "personal-member2",
            "shared-by-member2",
        }

    def test_admin_sees_all_regardless_of_privacy_level(self, db_session):
        family, admin, member_1, member_2 = _create_family_and_users(
            db_session,
            models.PrivacyLevel.PRIVATE,
        )
        _create_accounts_and_transactions(db_session, family, member_1, member_2)

        rows = get_family_transactions(db_session, family.id, admin, skip=0, limit=100)

        descriptions = {row.description for row in rows}
        assert descriptions == {
            "personal-member1",
            "personal-member2",
            "shared-by-member2",
        }
