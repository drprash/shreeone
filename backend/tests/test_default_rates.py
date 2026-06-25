"""
G2: DEFAULT_RATES expansion — verify coverage and cross-rate arithmetic.

No DB required; these are pure unit tests against the in-memory dict.
"""
from decimal import Decimal
import pytest
from app.financial_logic import FinancialEngine


RATES = FinancialEngine.DEFAULT_RATES

# Currencies that must be present after the expansion
EXPECTED_CURRENCIES = [
    # Original 9
    "USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "AED", "THB",
    # Gulf additions
    "SAR", "OMR", "KWD", "BHD", "QAR",
    # South/SE Asia additions
    "BDT", "PKR", "LKR", "NPR", "SGD", "MYR", "PHP", "IDR",
    # East Asia additions
    "CNY", "HKD", "KRW", "TWD",
    # Europe additions
    "CHF", "SEK", "NOK", "DKK", "PLN", "CZK",
    # Americas/Africa/Oceania
    "BRL", "MXN", "ZAR", "KES", "NGN", "NZD",
]


def test_all_expected_currencies_present():
    missing = [c for c in EXPECTED_CURRENCIES if c not in RATES]
    assert not missing, f"Missing from DEFAULT_RATES: {missing}"


def test_total_currency_count():
    assert len(RATES) >= 38, f"Expected at least 38 currencies, got {len(RATES)}"


def test_all_rates_positive():
    for currency, rate in RATES.items():
        assert rate > 0, f"{currency} has non-positive rate: {rate}"


def test_usd_is_base():
    assert RATES["USD"] == Decimal("1.0"), "USD must be 1.0 (base reference)"


def test_gulf_pegged_currencies_reasonable():
    """Gulf currencies pegged to USD should be within a tight range."""
    # AED: 1 USD ≈ 3.67 AED → 1 AED ≈ 0.272 USD
    assert Decimal("0.26") < RATES["AED"] < Decimal("0.28"), f"AED rate unexpected: {RATES['AED']}"
    # SAR: 1 USD ≈ 3.75 SAR → 1 SAR ≈ 0.267 USD
    assert Decimal("0.25") < RATES["SAR"] < Decimal("0.28"), f"SAR rate unexpected: {RATES['SAR']}"
    # QAR: 1 USD ≈ 3.64 QAR → 1 QAR ≈ 0.275 USD
    assert Decimal("0.26") < RATES["QAR"] < Decimal("0.29"), f"QAR rate unexpected: {RATES['QAR']}"


def test_high_value_currencies():
    """KWD and OMR are worth more than 1 USD."""
    assert RATES["KWD"] > Decimal("3.0"), f"KWD should be > 3 USD, got {RATES['KWD']}"
    assert RATES["OMR"] > Decimal("2.5"), f"OMR should be > 2.5 USD, got {RATES['OMR']}"
    assert RATES["BHD"] > Decimal("2.5"), f"BHD should be > 2.5 USD, got {RATES['BHD']}"


def test_cross_rate_gbp_to_eur():
    """1 GBP / 1 EUR should give a plausible GBP→EUR rate (~1.16)."""
    rate = RATES["GBP"] / RATES["EUR"]
    assert Decimal("1.0") < rate < Decimal("1.4"), f"GBP→EUR cross-rate implausible: {rate}"


def test_cross_rate_kwd_to_inr():
    """1 KWD should be worth roughly 250-300 INR."""
    rate = RATES["KWD"] / RATES["INR"]
    assert Decimal("200") < rate < Decimal("350"), f"KWD→INR cross-rate implausible: {rate}"


def test_cross_rate_aed_to_inr():
    """1 AED should be worth roughly 20-25 INR."""
    rate = RATES["AED"] / RATES["INR"]
    assert Decimal("18") < rate < Decimal("28"), f"AED→INR cross-rate implausible: {rate}"


def test_get_exchange_rate_uses_default_rates_as_fallback(tmp_path):
    """get_exchange_rate without a DB family_id must fall back to DEFAULT_RATES."""
    # Pass db=None — the method skips DB lookup when family_id is None
    rate = FinancialEngine.get_exchange_rate(None, "GBP", "USD", family_id=None)
    assert rate == RATES["GBP"], f"Expected GBP default rate {RATES['GBP']}, got {rate}"


def test_get_exchange_rate_same_currency_returns_one():
    rate = FinancialEngine.get_exchange_rate(None, "EUR", "EUR", family_id=None)
    assert rate == Decimal("1.0")


def test_new_currencies_not_silently_falling_back_to_one():
    """No new currency should accidentally return 1.0 (the silent-fallback sentinel)."""
    new_currencies = ["SAR", "OMR", "KWD", "BDT", "PKR", "SGD", "CNY", "ZAR", "KES", "NGN"]
    for c in new_currencies:
        rate = FinancialEngine.get_exchange_rate(None, c, "USD", family_id=None)
        assert rate != Decimal("1.0") or c == "USD", (
            f"{c}→USD returned 1.0 — missing from DEFAULT_RATES or equal to USD by coincidence?"
        )
