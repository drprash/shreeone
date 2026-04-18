"""
Exchange rate service — ECB + FloatRates dual-source integration.

Primary source: European Central Bank XML feed (no API key, ~30 currencies via EUR pivot).
Fallback source: FloatRates.com JSON feed (no API key, 150+ currencies including Gulf and
South Asian currencies absent from ECB: AED, BDT, BHD, KES, KWD, LKR, NPR, OMR, PKR, QAR, SAR).

Rate resolution order at fetch time (fetch_family_rates):
  1. ECB cross-rate via EUR pivot
  2. FloatRates direct lookup for ECB-uncovered pairs
  3. FloatRates inverse lookup (1/rate) if only the reverse pair is available

Rate resolution order at query time (FinancialEngine.get_exchange_rate):
  1. Stored rate for exact date
  2. Most recent stored rate within 7 days (stale-rate warning)
  3. FinancialEngine.DEFAULT_RATES (hardcoded approximates)
  4. User-supplied manual rate on transaction entry

Disabling auto-fetch (e.g. via a config flag) is possible but not yet implemented.
If added in future, note that DEFAULT_RATES in FinancialEngine covers only 9 currencies —
families using currencies outside that list (OMR, SAR, etc.) would get silent 1.0
fallbacks, causing incorrect dashboard totals and transaction conversions.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict

from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal

log = logging.getLogger(__name__)

ECB_FEED_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
STALE_RATE_DAYS = 7


def _fetch_ecb_rates() -> Optional[Dict[str, Decimal]]:
    """Fetch EUR-based rates from ECB XML feed. Returns {currency: rate_vs_EUR} or None on failure."""
    try:
        import requests  # imported lazily so missing dep doesn't break import
        resp = requests.get(ECB_FEED_URL, timeout=15)
        resp.raise_for_status()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        ns = {"ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        rates: Dict[str, Decimal] = {"EUR": Decimal("1.0")}
        for cube in root.iter("{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}Cube"):
            currency = cube.get("currency")
            rate = cube.get("rate")
            if currency and rate:
                try:
                    rates[currency] = Decimal(rate)
                except Exception:
                    pass
        log.info("ECB feed fetched: %d currencies", len(rates))
        return rates
    except Exception as exc:
        log.warning("ECB feed fetch failed: %s", exc)
        return None


def _compute_cross_rate(
    from_currency: str,
    to_currency: str,
    eur_rates: Dict[str, Decimal],
) -> Optional[Decimal]:
    """Compute cross-rate from_currency → to_currency using EUR as pivot."""
    if from_currency == to_currency:
        return Decimal("1.0")
    from_vs_eur = eur_rates.get(from_currency)
    to_vs_eur = eur_rates.get(to_currency)
    if from_vs_eur is None or to_vs_eur is None or to_vs_eur == 0:
        return None
    # from_currency per EUR: 1/from_vs_eur → EUR → to_currency
    # to_amount = from_amount * (to_vs_eur / from_vs_eur)
    return to_vs_eur / from_vs_eur


def _fetch_floatrates(base_currency: str) -> Optional[Dict[str, Decimal]]:
    """Fetch rates from FloatRates.com for currencies not covered by ECB.

    Returns {CURRENCY_CODE: rate} where rate = amount of that currency per 1 base_currency.
    FloatRates covers Gulf and South Asian currencies absent from the ECB feed
    (AED, BDT, BHD, KES, KWD, LKR, NPR, OMR, PKR, QAR, SAR, …).
    """
    try:
        import requests
        url = f"https://www.floatrates.com/daily/{base_currency.lower()}.json"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rates: Dict[str, Decimal] = {}
        for entry in data.values():
            try:
                code = entry.get("code") or entry.get("alphaCode")
                rate = entry.get("rate")
                if code and rate is not None:
                    rates[code.upper()] = Decimal(str(rate))
            except Exception:
                pass
        log.info("FloatRates fetched for %s: %d currencies", base_currency, len(rates))
        return rates if rates else None
    except Exception as exc:
        log.warning("FloatRates fetch failed for %s: %s", base_currency, exc)
        return None


def _upsert_rate(
    db: Session,
    family_id,
    from_currency: str,
    to_currency: str,
    rate: Decimal,
    valid_date: date,
    source: models.ExchangeRateSource,
) -> None:
    """Insert or update a rate row (upsert on the unique constraint)."""
    existing = (
        db.query(models.ExchangeRate)
        .filter(
            models.ExchangeRate.family_id == family_id,
            models.ExchangeRate.from_currency == from_currency,
            models.ExchangeRate.to_currency == to_currency,
            models.ExchangeRate.valid_date == valid_date,
        )
        .first()
    )
    if existing:
        existing.rate = rate
        existing.source = source
        existing.fetched_at = datetime.utcnow()
    else:
        db.add(
            models.ExchangeRate(
                family_id=family_id,
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                source=source,
                valid_date=valid_date,
                fetched_at=datetime.utcnow(),
            )
        )


def fetch_family_rates(db: Session, family: models.Family) -> int:
    """
    Fetch and store exchange rates for a single family's base + secondary currencies.

    Primary source: ECB XML feed (covers ~30 major currencies via EUR pivot).
    Fallback source: FloatRates.com (covers Gulf + South Asian currencies absent from ECB).

    Returns the number of rate pairs stored/updated.
    """
    secondary = [fc.currency_code for fc in family.family_currencies]
    all_currencies = list({family.base_currency} | set(secondary))

    if len(all_currencies) <= 1:
        return 0  # Nothing to convert

    eur_rates = _fetch_ecb_rates()  # None if ECB is unreachable

    today = date.today()
    count = 0
    pairs = set()
    missing_pairs: set = set()  # pairs ECB could not fill

    for fc in all_currencies:
        for tc in all_currencies:
            if fc == tc or (fc, tc) in pairs:
                continue
            pairs.add((fc, tc))
            pairs.add((tc, fc))

            rate_ft = _compute_cross_rate(fc, tc, eur_rates) if eur_rates else None
            rate_tf = _compute_cross_rate(tc, fc, eur_rates) if eur_rates else None

            if rate_ft is not None:
                _upsert_rate(db, family.id, fc, tc, rate_ft, today, models.ExchangeRateSource.AUTO_FETCHED)
                count += 1
            else:
                missing_pairs.add((fc, tc))

            if rate_tf is not None:
                _upsert_rate(db, family.id, tc, fc, rate_tf, today, models.ExchangeRateSource.AUTO_FETCHED)
                count += 1
            else:
                missing_pairs.add((tc, fc))

    # Fill ECB gaps using FloatRates
    if missing_pairs:
        # Fetch FloatRates once per unique from_currency to minimise HTTP calls
        floatrates_cache: Dict[str, Dict[str, Decimal]] = {}
        for base in {fc for fc, _ in missing_pairs}:
            fetched = _fetch_floatrates(base)
            if fetched:
                floatrates_cache[base] = fetched

        for fc, tc in missing_pairs:
            rate = None
            if fc in floatrates_cache:
                # Direct lookup: fc→tc rate from FloatRates for fc
                rate = floatrates_cache[fc].get(tc)
            if rate is None and tc in floatrates_cache:
                # Inverse lookup: use tc→fc rate and invert
                inv = floatrates_cache[tc].get(fc)
                if inv and inv != 0:
                    rate = Decimal("1") / inv
            if rate is not None:
                _upsert_rate(db, family.id, fc, tc, rate, today, models.ExchangeRateSource.AUTO_FETCHED)
                count += 1

        if not floatrates_cache:
            log.warning(
                "FloatRates fallback also failed for family %s — %d pairs unresolved",
                family.id, len(missing_pairs),
            )

    if count == 0:
        log.warning("No rates stored for family %s — all sources failed or unavailable", family.id)

    db.commit()
    return count


RATE_RETENTION_DAYS = 14  # Anything older than the stale window (7d) has no functional use


def _prune_old_rates(db: Session) -> int:
    """Delete exchange rate rows older than RATE_RETENTION_DAYS. Returns count deleted."""
    cutoff = date.today() - timedelta(days=RATE_RETENTION_DAYS)
    deleted = (
        db.query(models.ExchangeRate)
        .filter(models.ExchangeRate.valid_date < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def fetch_all_family_rates() -> None:
    """APScheduler entry point — runs for every active family."""
    db = SessionLocal()
    try:
        families = (
            db.query(models.Family)
            .filter(models.Family.deleted_at.is_(None))
            .all()
        )
        total = 0
        for family in families:
            try:
                n = fetch_family_rates(db, family)
                total += n
            except Exception as exc:
                log.error("Rate fetch failed for family %s: %s", family.id, exc)
        log.info("Exchange rate fetch complete: %d pairs updated across %d families", total, len(families))

        pruned = _prune_old_rates(db)
        if pruned:
            log.info("Exchange rate pruning: removed %d rows older than %d days", pruned, RATE_RETENTION_DAYS)
    finally:
        db.close()


def get_stored_rate(
    db: Session,
    family_id,
    from_currency: str,
    to_currency: str,
    for_date: Optional[date] = None,
) -> Optional[Decimal]:
    """
    Look up the best available stored rate.
    1. Exact date match
    2. Most recent within STALE_RATE_DAYS
    Returns None if nothing usable found.
    """
    if from_currency == to_currency:
        return Decimal("1.0")

    target_date = for_date or date.today()

    # Exact date
    row = (
        db.query(models.ExchangeRate)
        .filter(
            models.ExchangeRate.family_id == family_id,
            models.ExchangeRate.from_currency == from_currency,
            models.ExchangeRate.to_currency == to_currency,
            models.ExchangeRate.valid_date == target_date,
        )
        .first()
    )
    if row:
        return Decimal(str(row.rate))

    # Most recent within stale window
    cutoff = target_date - timedelta(days=STALE_RATE_DAYS)
    row = (
        db.query(models.ExchangeRate)
        .filter(
            models.ExchangeRate.family_id == family_id,
            models.ExchangeRate.from_currency == from_currency,
            models.ExchangeRate.to_currency == to_currency,
            models.ExchangeRate.valid_date >= cutoff,
            models.ExchangeRate.valid_date <= target_date,
        )
        .order_by(models.ExchangeRate.valid_date.desc())
        .first()
    )
    if row:
        log.debug(
            "Using stale rate %s→%s from %s (target %s)",
            from_currency, to_currency, row.valid_date, target_date,
        )
        return Decimal(str(row.rate))

    return None
