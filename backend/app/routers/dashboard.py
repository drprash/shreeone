from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from decimal import Decimal
from datetime import date
from app import schemas, models, auth
from app.database import get_db
from app.financial_logic import FinancialEngine

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/", response_model=schemas.DashboardData)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return FinancialEngine.get_family_dashboard_data(db, current_user.family_id, current_user)

@router.get("/summary", response_model=schemas.DashboardSummary)
def get_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    data = FinancialEngine.get_family_dashboard_data(db, current_user.family_id, current_user)
    return data.summary

@router.get("/country-breakdown", response_model=schemas.DashboardDataWithCountry)
def get_dashboard_with_country(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Dashboard data extended with a net-worth-by-country breakdown."""
    from app.exchange_rate_service import get_stored_rate
    from sqlalchemy import or_

    base_data = FinancialEngine.get_family_dashboard_data(db, current_user.family_id, current_user)
    base_currency = current_user.family.base_currency

    # Build country totals across all accessible, included accounts
    family_id = current_user.family_id
    privacy_level = current_user.family.privacy_level

    account_q = db.query(models.Account).filter(
        models.Account.family_id == family_id,
        models.Account.deleted_at.is_(None),
    )
    if current_user.role != models.Role.ADMIN:
        if privacy_level == models.PrivacyLevel.PRIVATE:
            account_q = account_q.filter(models.Account.owner_user_id == current_user.id)
        elif privacy_level == models.PrivacyLevel.SHARED:
            account_q = account_q.filter(
                or_(
                    models.Account.owner_type == models.OwnerType.SHARED,
                    models.Account.owner_user_id == current_user.id,
                )
            )

    accounts = account_q.all()

    country_totals: dict = {}

    for account in accounts:
        # Mirror get_family_dashboard_data: non-admins skip excluded accounts
        if not account.include_in_family_overview and current_user.role != models.Role.ADMIN:
            continue

        balance = account.current_balance or Decimal("0")
        if account.currency != base_currency:
            rate = FinancialEngine.get_exchange_rate(
                db, account.currency, base_currency, family_id=family_id
            )
            balance_base = balance * rate
        else:
            balance_base = balance

        key = account.country_code  # None → "Other / Unassigned"

        # Liabilities (e.g. credit cards) reduce net worth — subtract as in the net worth tile
        if account.type in models.LIABILITY_ACCOUNT_TYPES:
            country_totals[key] = country_totals.get(key, Decimal("0")) - balance_base
        else:
            country_totals[key] = country_totals.get(key, Decimal("0")) + balance_base

    # Country name lookup
    COUNTRY_NAMES = {
        "IN": "India", "US": "United States", "GB": "United Kingdom",
        "AE": "UAE", "SG": "Singapore", "CA": "Canada", "AU": "Australia",
        "NZ": "New Zealand", "QA": "Qatar", "SA": "Saudi Arabia",
        "DE": "Germany", "FR": "France", "NL": "Netherlands", "CH": "Switzerland",
        "HK": "Hong Kong", "JP": "Japan", "MY": "Malaysia", "TH": "Thailand",
    }

    breakdown = []
    for code, total in sorted(country_totals.items(), key=lambda x: x[1], reverse=True):
        breakdown.append(
            schemas.CountryBreakdown(
                country_code=code,
                country_name=COUNTRY_NAMES.get(code) if code else None,
                total_in_base=total,
                base_currency=base_currency,
            )
        )

    # Most recent rate date for the family
    latest_row = (
        db.query(models.ExchangeRate)
        .filter(models.ExchangeRate.family_id == family_id)
        .order_by(models.ExchangeRate.valid_date.desc())
        .first()
    )
    rates_as_of = latest_row.valid_date if latest_row else None

    return schemas.DashboardDataWithCountry(
        summary=base_data.summary,
        category_breakdown=base_data.category_breakdown,
        member_spending=base_data.member_spending,
        recent_transactions=base_data.recent_transactions,
        country_breakdown=breakdown,
        rates_as_of=rates_as_of,
    )


@router.get("/net-worth-history", response_model=list[schemas.NetWorthSnapshotResponse])
def net_worth_history(
    months: int = 12,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return the last N months of daily net worth snapshots for the current family."""
    from datetime import timedelta, datetime as dt
    cutoff = dt.utcnow().date() - timedelta(days=months * 31)
    return (
        db.query(models.NetWorthSnapshot)
        .filter(
            models.NetWorthSnapshot.family_id == current_user.family_id,
            models.NetWorthSnapshot.snapshot_date >= cutoff,
        )
        .order_by(models.NetWorthSnapshot.snapshot_date.asc())
        .all()
    )


@router.get("/stale-valuations", response_model=list[dict])
def stale_valuations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return investment/property accounts that haven't been valued in 30+ days."""
    from datetime import timedelta, datetime as dt
    threshold = dt.utcnow() - timedelta(days=30)
    stale = db.query(models.Account).filter(
        models.Account.family_id == current_user.family_id,
        models.Account.deleted_at.is_(None),
        models.Account.type.in_([
            models.AccountType.MUTUAL_FUND,
            models.AccountType.STOCK_PORTFOLIO,
            models.AccountType.PROVIDENT_FUND,
            models.AccountType.PROPERTY,
            models.AccountType.FIXED_DEPOSIT,
        ]),
        (models.Account.last_valued_at.is_(None)) | (models.Account.last_valued_at < threshold),
    ).all()
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "type": a.type.value,
            "last_valued_at": a.last_valued_at.isoformat() if a.last_valued_at else None,
        }
        for a in stale
    ]


@router.get("/member/{member_id}", response_model=schemas.DashboardSummary)
def get_member_summary(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    """Return dashboard summary scoped to a single family member. Admin only."""
    member = db.query(models.User).filter(
        models.User.id == member_id,
        models.User.family_id == current_user.family_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return FinancialEngine.get_member_dashboard_summary(
        db,
        family_id=str(current_user.family_id),
        member_id=str(member_id),
        base_currency=current_user.family.base_currency
    )
