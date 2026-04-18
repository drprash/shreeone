"""
Tests for liability account logic:
- Bank→CC transfer correctly reduces CC balance (the core reported scenario)
- CC→Bank transfer correctly increases CC balance (cash advance)
- adjust-balance on a liability: reducing debt creates INCOME, increasing creates EXPENSE
- account_class field is ASSET or LIABILITY based on account type
"""
from datetime import datetime
from decimal import Decimal
import uuid

import pytest

from app import models, crud
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


def _seed(db):
    """Seed a family, admin user, bank account ($500), and credit card ($200 debt)."""
    family = models.Family(
        id=uuid.uuid4(),
        name="Test Family",
        base_currency="USD",
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(family)

    admin = models.User(
        id=uuid.uuid4(),
        family_id=family.id,
        first_name="Admin",
        last_name="User",
        email=f"admin-{uuid.uuid4()}@test.com",
        role=models.Role.ADMIN,
        active=True,
        activated=True,
        password_required=False,
    )
    db.add(admin)

    bank = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Checking",
        type=models.AccountType.BANK,
        currency="USD",
        owner_type=models.OwnerType.SHARED,
        opening_balance=Decimal("500.00"),
        current_balance=Decimal("500.00"),
        include_in_family_overview=True,
    )
    cc = models.Account(
        id=uuid.uuid4(),
        family_id=family.id,
        name="Visa",
        type=models.AccountType.CREDIT_CARD,
        currency="USD",
        owner_type=models.OwnerType.SHARED,
        opening_balance=Decimal("200.00"),  # $200 existing debt
        current_balance=Decimal("200.00"),
        include_in_family_overview=True,
    )
    db.add(bank)
    db.add(cc)
    db.commit()
    return family, admin, bank, cc


def _make_transfer(db, *, source_account, target_account, amount, user_id):
    """Create a paired transfer transaction and update both account balances,
    mirroring what the transactions router does via FinancialEngine.process_transaction."""
    tx_date = datetime.utcnow()
    source_tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=source_account.id,
        created_by_user_id=user_id,
        type=models.TransactionType.TRANSFER,
        amount=amount,
        currency=source_account.currency,
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=amount,
        transaction_date=tx_date,
        is_source_transaction=True,
    )
    db.add(source_tx)
    db.flush()

    target_tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=target_account.id,
        created_by_user_id=user_id,
        type=models.TransactionType.TRANSFER,
        amount=amount,
        currency=target_account.currency,
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=amount,
        transaction_date=tx_date,
        linked_transaction_id=source_tx.id,
        is_source_transaction=False,
    )
    db.add(target_tx)
    db.flush()

    source_tx.linked_transaction_id = target_tx.id
    db.commit()

    # Update stored balances so the dashboard (which reads current_balance for
    # asset accounts) reflects the new state, matching what the router does.
    FinancialEngine.update_account_balance(db, str(source_account.id))
    FinancialEngine.update_account_balance(db, str(target_account.id))

    return source_tx, target_tx


# ---------------------------------------------------------------------------
# Transfer tests
# ---------------------------------------------------------------------------

def test_bank_to_cc_payment_reduces_cc_balance_to_zero(db_session):
    """
    Core scenario: CC owes $200, user transfers $200 from Bank → CC.
    Bank balance: 500 - 200 = 300.
    CC balance:   200 - 200 = 0.
    """
    _, admin, bank, cc = _seed(db_session)

    _make_transfer(db_session, source_account=bank, target_account=cc,
                   amount=Decimal("200.00"), user_id=admin.id)

    cc_balance = FinancialEngine.calculate_account_balance(db_session, str(cc.id))
    bank_balance = FinancialEngine.calculate_account_balance(db_session, str(bank.id))

    assert cc_balance == Decimal("0.00"), f"Expected CC balance 0, got {cc_balance}"
    assert bank_balance == Decimal("300.00"), f"Expected bank balance 300, got {bank_balance}"


def test_bank_to_cc_partial_payment_reduces_cc_balance(db_session):
    """Partial payment: CC owes $200, pay $80 → CC owes $120."""
    _, admin, bank, cc = _seed(db_session)

    _make_transfer(db_session, source_account=bank, target_account=cc,
                   amount=Decimal("80.00"), user_id=admin.id)

    cc_balance = FinancialEngine.calculate_account_balance(db_session, str(cc.id))
    assert cc_balance == Decimal("120.00")


def test_cc_to_bank_cash_advance_increases_cc_balance(db_session):
    """Cash advance: CC balance starts at $200, cash advance $50 → CC owes $250."""
    _, admin, bank, cc = _seed(db_session)

    _make_transfer(db_session, source_account=cc, target_account=bank,
                   amount=Decimal("50.00"), user_id=admin.id)

    cc_balance = FinancialEngine.calculate_account_balance(db_session, str(cc.id))
    assert cc_balance == Decimal("250.00")


def test_payment_reflected_in_dashboard_net_worth(db_session):
    """After paying off CC, liability drops to 0 and net worth improves."""
    family, admin, bank, cc = _seed(db_session)

    # Before payment: net worth = 500 (bank) - 200 (cc debt) = 300
    data_before = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)
    assert data_before.summary.total_credit_liability == Decimal("200.00")
    assert data_before.summary.total_net_worth == Decimal("300.00")

    _make_transfer(db_session, source_account=bank, target_account=cc,
                   amount=Decimal("200.00"), user_id=admin.id)

    # After payment: net worth = 300 (bank) - 0 (cc debt) = 300 (unchanged overall)
    data_after = FinancialEngine.get_family_dashboard_data(db_session, str(family.id), admin)
    assert data_after.summary.total_credit_liability == Decimal("0.00")
    assert data_after.summary.total_net_worth == Decimal("300.00")


# ---------------------------------------------------------------------------
# adjust-balance logic tests (via FinancialEngine directly)
# ---------------------------------------------------------------------------

def test_income_transaction_on_liability_reduces_balance(db_session):
    """
    INCOME on a liability account (simulating what adjust-balance does when
    user wants to reduce CC balance) should lower the balance.
    CC at $200, add INCOME $200 → balance = 0.
    """
    _, admin, _, cc = _seed(db_session)

    income_tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=cc.id,
        created_by_user_id=admin.id,
        type=models.TransactionType.INCOME,
        amount=Decimal("200.00"),
        currency="USD",
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal("200.00"),
        transaction_date=datetime.utcnow(),
        is_source_transaction=True,
    )
    db_session.add(income_tx)
    db_session.commit()

    balance = FinancialEngine.calculate_account_balance(db_session, str(cc.id))
    assert balance == Decimal("0.00")


def test_expense_transaction_on_liability_increases_balance(db_session):
    """
    EXPENSE on a liability account increases debt.
    CC at $200, add EXPENSE $50 → balance = 250.
    """
    _, admin, _, cc = _seed(db_session)

    expense_tx = models.Transaction(
        id=uuid.uuid4(),
        account_id=cc.id,
        created_by_user_id=admin.id,
        type=models.TransactionType.EXPENSE,
        amount=Decimal("50.00"),
        currency="USD",
        exchange_rate_to_base=Decimal("1"),
        amount_in_base_currency=Decimal("50.00"),
        transaction_date=datetime.utcnow(),
        is_source_transaction=True,
    )
    db_session.add(expense_tx)
    db_session.commit()

    balance = FinancialEngine.calculate_account_balance(db_session, str(cc.id))
    assert balance == Decimal("250.00")


# ---------------------------------------------------------------------------
# LIABILITY_ACCOUNT_TYPES membership
# ---------------------------------------------------------------------------

def test_credit_card_is_in_liability_account_types():
    assert models.AccountType.CREDIT_CARD in models.LIABILITY_ACCOUNT_TYPES


def test_bank_cash_investment_are_not_liabilities():
    for acct_type in (
        models.AccountType.BANK,
        models.AccountType.CASH,
        models.AccountType.INVESTMENT,
    ):
        assert acct_type not in models.LIABILITY_ACCOUNT_TYPES
