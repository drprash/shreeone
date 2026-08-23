"""
Tests for the medium-severity 2026-08 audit fixes:

1. Historical exchange rates are retained (not pruned) so backdated
   transactions can look up the rate for their date
2. Accounts flagged include_in_family_overview=False are excluded from the
   family dashboard net worth for admins too (matching the snapshot task)
3. Converting an unknown currency logs a warning instead of failing silently
4. Transaction categories are validated: family ownership, type match,
   and no categories on transfers
"""
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from app import models, schemas, crud
from app import exchange_rate_service
from app.financial_logic import FinancialEngine

from test_financial_audit_fixes import (  # noqa: F401  (db_session fixture)
    db_session, _make_family, _make_account, _make_tx, _store_rate,
)


# ── 1. Historical rate retention ─────────────────────────────────────────────

def test_old_stored_rates_survive_rate_fetch_cycle(db_session):
    """Rates older than the stale window must not be deleted — backdated
    transactions look them up via get_stored_rate(for_date=...)."""
    family, _, _ = _make_family(db_session, base_currency="USD")
    old_date = date.today() - timedelta(days=30)
    _store_rate(db_session, family, "AED", "USD", "0.27", valid=old_date)

    with patch.object(exchange_rate_service, "_fetch_ecb_rates", return_value=None), \
         patch.object(exchange_rate_service, "_fetch_floatrates", return_value=None):
        exchange_rate_service.fetch_all_family_rates()

    surviving = db_session.query(models.ExchangeRate).filter(
        models.ExchangeRate.family_id == family.id,
        models.ExchangeRate.valid_date == old_date,
    ).count()
    assert surviving == 1

    rate = exchange_rate_service.get_stored_rate(
        db_session, family.id, "AED", "USD", for_date=old_date
    )
    assert rate == Decimal("0.27")


# ── 2. include_in_family_overview honored for admins ─────────────────────────

def test_admin_dashboard_excludes_flagged_accounts(db_session):
    """The admin's net worth tile must match the snapshot task, which skips
    accounts excluded from the family overview."""
    family, admin, _ = _make_family(db_session, base_currency="USD")
    _make_account(db_session, family, owner=admin, opening=Decimal("1000"))
    hidden = _make_account(db_session, family, owner=admin, opening=Decimal("500"))
    hidden.include_in_family_overview = False
    db_session.commit()

    data = FinancialEngine.get_family_dashboard_data(db_session, family.id, admin)
    assert data.summary.total_net_worth == Decimal("1000.00")


# ── 3. Unknown currency warning ──────────────────────────────────────────────

def test_unknown_currency_conversion_logs_warning(db_session, caplog):
    with caplog.at_level(logging.WARNING, logger="app.financial_logic"):
        rate = FinancialEngine.get_exchange_rate(db_session, "XXX", "USD")
    assert rate == Decimal("1.0")
    assert any("XXX" in record.message for record in caplog.records)


def test_known_currency_conversion_does_not_warn(db_session, caplog):
    with caplog.at_level(logging.WARNING, logger="app.financial_logic"):
        FinancialEngine.get_exchange_rate(db_session, "EUR", "USD")
    assert not caplog.records


# ── 4. Category validation ───────────────────────────────────────────────────

def _make_category(db, family, cat_type=models.CategoryType.EXPENSE):
    category = models.Category(
        id=uuid.uuid4(), family_id=family.id,
        name=f"Cat-{uuid.uuid4().hex[:6]}", type=cat_type,
    )
    db.add(category)
    db.commit()
    return category


def _tx_create(account, category=None, tx_type=models.TransactionType.EXPENSE, **kwargs):
    return schemas.TransactionCreate(
        type=tx_type,
        amount=Decimal("50"),
        currency=account.currency,
        account_id=account.id,
        category_id=category.id if category else None,
        transaction_date=datetime.utcnow(),
        **kwargs,
    )


def test_create_rejects_cross_family_category(db_session):
    family_a, admin_a, _ = _make_family(db_session)
    family_b, _, _ = _make_family(db_session)
    account = _make_account(db_session, family_a, owner=admin_a)
    foreign_category = _make_category(db_session, family_b)

    with pytest.raises(ValueError):
        FinancialEngine.process_transaction(
            db_session, admin_a, _tx_create(account, foreign_category)
        )


def test_create_rejects_type_mismatched_category(db_session):
    family, admin, _ = _make_family(db_session)
    account = _make_account(db_session, family, owner=admin)
    income_category = _make_category(db_session, family, models.CategoryType.INCOME)

    with pytest.raises(ValueError):
        FinancialEngine.process_transaction(
            db_session, admin, _tx_create(account, income_category)
        )


def test_create_rejects_category_on_transfer(db_session):
    family, admin, _ = _make_family(db_session)
    source = _make_account(db_session, family, owner=admin)
    target = _make_account(db_session, family, owner=admin)
    category = _make_category(db_session, family)

    with pytest.raises(ValueError):
        FinancialEngine.process_transaction(
            db_session, admin,
            _tx_create(source, category,
                       tx_type=models.TransactionType.TRANSFER,
                       target_account_id=target.id),
        )


def test_create_accepts_matching_category(db_session):
    family, admin, _ = _make_family(db_session)
    account = _make_account(db_session, family, owner=admin)
    category = _make_category(db_session, family, models.CategoryType.EXPENSE)

    tx, _ = FinancialEngine.process_transaction(
        db_session, admin, _tx_create(account, category)
    )
    assert tx.category_id == category.id


def test_update_rejects_type_mismatched_category(db_session):
    family, admin, _ = _make_family(db_session)
    account = _make_account(db_session, family, owner=admin)
    tx = _make_tx(db_session, account, admin, 50, "USD", 1)
    income_category = _make_category(db_session, family, models.CategoryType.INCOME)

    update = schemas.TransactionUpdate(category_id=income_category.id)
    with pytest.raises(ValueError):
        crud.update_transaction(db_session, tx.id, update, admin)


def test_update_rejects_cross_family_category(db_session):
    family_a, admin_a, _ = _make_family(db_session)
    family_b, _, _ = _make_family(db_session)
    account = _make_account(db_session, family_a, owner=admin_a)
    tx = _make_tx(db_session, account, admin_a, 50, "USD", 1)
    foreign_category = _make_category(db_session, family_b)

    update = schemas.TransactionUpdate(category_id=foreign_category.id)
    with pytest.raises(ValueError):
        crud.update_transaction(db_session, tx.id, update, admin_a)
