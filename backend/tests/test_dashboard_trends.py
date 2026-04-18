from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import pytest

from app import models
from app.database import SessionLocal, Base, engine
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


def _seed_family_with_admin(db):
    family = models.Family(
        id=uuid.uuid4(),
        name="Trend Family",
        base_currency="USD",
        privacy_level=models.PrivacyLevel.FAMILY,
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
    db.add(admin)

    account = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Main",
        type=models.AccountType.BANK,
        currency="USD",
        owner_type=models.OwnerType.SHARED,
        opening_balance=Decimal("0"),
        current_balance=Decimal("0"),
        include_in_family_overview=True,
    )
    db.add(account)
    db.commit()

    return family, admin, account


def _add_tx(
    db,
    *,
    account_id,
    user_id,
    tx_type,
    amount,
    tx_date,
):
    tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=account_id,
        created_by_user_id=user_id,
        type=tx_type,
        amount=Decimal(amount),
        currency="USD",
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal(amount),
        transaction_date=tx_date,
        is_source_transaction=True,
    )
    db.add(tx)


class TestDashboardTrends:
    def test_credit_liability_is_positive_owed_amount(self, db_session):
        """Credit liability = sum of expenses on credit cards (debt).
        With the corrected sign convention, expenses INCREASE credit card
        balance (positive = debt owed).
        """
        family = models.Family(
            id=uuid.uuid4(),
            name="Credit Family",
            base_currency="USD",
            privacy_level=models.PrivacyLevel.FAMILY,
        )
        db_session.add(family)

        admin = models.User(
            id=uuid.uuid4(),
            family_id=family.id,
            first_name="Admin",
            last_name="User",
            email=f"credit-admin-{uuid.uuid4()}@example.com",
            role=models.Role.ADMIN,
            active=True,
            activated=True,
            password_required=False,
        )
        db_session.add(admin)

        credit_account = models.Account(
            id=uuid.uuid4(),
            family_id=family.id,
            name="Card",
            type=models.AccountType.CREDIT_CARD,
            currency="USD",
            owner_type=models.OwnerType.SHARED,
            opening_balance=Decimal("0"),
            current_balance=Decimal("0"),
            include_in_family_overview=True,
        )
        db_session.add(credit_account)
        db_session.commit()

        now = datetime.utcnow()
        tx_date = now.replace(day=5, hour=12, minute=0, second=0, microsecond=0)

        # Add expense transactions on the credit card
        _add_tx(db_session, account_id=credit_account.id, user_id=admin.id,
                tx_type=models.TransactionType.EXPENSE, amount="100.00", tx_date=tx_date)
        _add_tx(db_session, account_id=credit_account.id, user_id=admin.id,
                tx_type=models.TransactionType.EXPENSE, amount="25.50", tx_date=tx_date)
        db_session.commit()

        data = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)

        # Credit liability should equal total expenses (positive = debt owed)
        assert data.summary.total_credit_liability == Decimal("125.50")
        # Credit card debt should reduce net worth
        assert data.summary.total_net_worth == Decimal("-125.50")

    def test_credit_liability_with_opening_balance(self, db_session):
        """Opening balance on credit card represents existing debt.
        Expenses add to it, payments reduce it.
        """
        family = models.Family(
            id=uuid.uuid4(),
            name="Credit OB Family",
            base_currency="USD",
            privacy_level=models.PrivacyLevel.FAMILY,
        )
        db_session.add(family)

        admin = models.User(
            id=uuid.uuid4(),
            family_id=family.id,
            first_name="Admin",
            last_name="User",
            email=f"credit-ob-{uuid.uuid4()}@example.com",
            role=models.Role.ADMIN,
            active=True,
            activated=True,
            password_required=False,
        )
        db_session.add(admin)

        credit_account = models.Account(
            id=uuid.uuid4(),
            family_id=family.id,
            name="Visa",
            type=models.AccountType.CREDIT_CARD,
            currency="USD",
            owner_type=models.OwnerType.SHARED,
            opening_balance=Decimal("500.00"),
            current_balance=Decimal("500.00"),
            include_in_family_overview=True,
        )
        db_session.add(credit_account)
        db_session.commit()

        now = datetime.utcnow()
        tx_date = now.replace(day=5, hour=12, minute=0, second=0, microsecond=0)

        # Expense adds to debt
        _add_tx(db_session, account_id=credit_account.id, user_id=admin.id,
                tx_type=models.TransactionType.EXPENSE, amount="200.00", tx_date=tx_date)
        # Payment (income) reduces debt
        _add_tx(db_session, account_id=credit_account.id, user_id=admin.id,
                tx_type=models.TransactionType.INCOME, amount="50.00", tx_date=tx_date)
        db_session.commit()

        data = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)

        # Credit liability = 500 (opening) + 200 (expense) - 50 (payment) = 650
        assert data.summary.total_credit_liability == Decimal("650.00")
        assert data.summary.total_net_worth == Decimal("-650.00")

    def test_non_credit_account_expense_not_added_to_credit_liability(self, db_session):
        family = models.Family(
            id=uuid.uuid4(),
            name="Mixed Accounts Family",
            base_currency="USD",
            privacy_level=models.PrivacyLevel.FAMILY,
        )
        db_session.add(family)

        admin = models.User(
            id=uuid.uuid4(),
            family_id=family.id,
            first_name="Admin",
            last_name="User",
            email=f"mixed-accounts-{uuid.uuid4()}@example.com",
            role=models.Role.ADMIN,
            active=True,
            activated=True,
            password_required=False,
        )
        db_session.add(admin)

        credit_account = models.Account(
            id=uuid.uuid4(),
            family_id=family.id,
            name="Card",
            type=models.AccountType.CREDIT_CARD,
            currency="USD",
            owner_type=models.OwnerType.SHARED,
            opening_balance=Decimal("0"),
            current_balance=Decimal("0"),
            include_in_family_overview=True,
        )
        bank_account = models.Account(
            id=uuid.uuid4(),
            family_id=family.id,
            name="Bank",
            type=models.AccountType.BANK,
            currency="USD",
            owner_type=models.OwnerType.SHARED,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
            include_in_family_overview=True,
        )
        db_session.add(credit_account)
        db_session.add(bank_account)
        db_session.commit()

        now = datetime.utcnow()
        tx_date = now.replace(day=5, hour=12, minute=0, second=0, microsecond=0)

        _add_tx(
            db_session,
            account_id=credit_account.id,
            user_id=admin.id,
            tx_type=models.TransactionType.EXPENSE,
            amount="120.00",
            tx_date=tx_date,
        )
        _add_tx(
            db_session,
            account_id=bank_account.id,
            user_id=admin.id,
            tx_type=models.TransactionType.EXPENSE,
            amount="300.00",
            tx_date=tx_date,
        )
        db_session.commit()

        data = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)

        assert data.summary.total_credit_liability == Decimal("120.00")

    def test_positive_income_trend(self, db_session):
        family, admin, account = _seed_family_with_admin(db_session)

        now = datetime.utcnow()
        current_month_date = now.replace(day=10, hour=12, minute=0, second=0, microsecond=0)
        previous_month_date = (current_month_date.replace(day=1) - timedelta(days=1)).replace(day=10)

        _add_tx(
            db_session,
            account_id=account.id,
            user_id=admin.id,
            tx_type=models.TransactionType.INCOME,
            amount="200.00",
            tx_date=current_month_date,
        )
        _add_tx(
            db_session,
            account_id=account.id,
            user_id=admin.id,
            tx_type=models.TransactionType.INCOME,
            amount="100.00",
            tx_date=previous_month_date,
        )
        db_session.commit()

        data = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)

        assert data.summary.monthly_income == Decimal("200.00")
        assert data.summary.monthly_income_trend == pytest.approx(100.0)

    def test_negative_expense_trend(self, db_session):
        family, admin, account = _seed_family_with_admin(db_session)

        now = datetime.utcnow()
        current_month_date = now.replace(day=11, hour=12, minute=0, second=0, microsecond=0)
        previous_month_date = (current_month_date.replace(day=1) - timedelta(days=1)).replace(day=11)

        _add_tx(
            db_session,
            account_id=account.id,
            user_id=admin.id,
            tx_type=models.TransactionType.EXPENSE,
            amount="50.00",
            tx_date=current_month_date,
        )
        _add_tx(
            db_session,
            account_id=account.id,
            user_id=admin.id,
            tx_type=models.TransactionType.EXPENSE,
            amount="100.00",
            tx_date=previous_month_date,
        )
        db_session.commit()

        data = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)

        assert data.summary.monthly_expense == Decimal("50.00")
        assert data.summary.monthly_expense_trend == pytest.approx(-50.0)

    def test_zero_previous_value_trend_rule(self, db_session):
        family, admin, account = _seed_family_with_admin(db_session)

        now = datetime.utcnow().replace(day=12, hour=12, minute=0, second=0, microsecond=0)

        _add_tx(
            db_session,
            account_id=account.id,
            user_id=admin.id,
            tx_type=models.TransactionType.INCOME,
            amount="100.00",
            tx_date=now,
        )
        db_session.commit()

        data = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)

        assert data.summary.monthly_income == Decimal("100.00")
        assert data.summary.monthly_income_trend == pytest.approx(100.0)
