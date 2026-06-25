from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import date, timedelta

from app import schemas, models
from app.database import get_db
from app.auth import get_current_user
from app.financial_logic import FinancialEngine

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=schemas.StatsResponse)
def get_stats(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    duration = (end_date - start_date).days + 1
    prior_end = start_date - timedelta(days=1)
    prior_start = prior_end - timedelta(days=duration - 1)

    family_id = str(current_user.family_id)

    current_data = FinancialEngine.get_period_stats(
        db, family_id, current_user, start_date, end_date
    )
    prior_data = FinancialEngine.get_period_stats(
        db, family_id, current_user, prior_start, prior_end
    )

    def pct_change(current_val, prior_val):
        if prior_val == 0:
            return None
        return round(float((current_val - prior_val) / prior_val * 100), 1)

    trends = schemas.StatsTrends(
        income_change_pct=pct_change(current_data['income'], prior_data['income']),
        expense_change_pct=pct_change(current_data['expenses'], prior_data['expenses']),
        savings_change_pct=(
            pct_change(current_data['savings'], prior_data['savings'])
            if prior_data['savings'] > 0 else None
        ),
    )

    return schemas.StatsResponse(
        base_currency=current_user.family.base_currency,
        period=schemas.StatsPeriod(start_date=start_date, end_date=end_date),
        prior_period=schemas.StatsPeriod(start_date=prior_start, end_date=prior_end),
        current=schemas.StatsCurrentData(
            income=current_data['income'],
            expenses=current_data['expenses'],
            savings=current_data['savings'],
            savings_rate=current_data['savings_rate'],
            categories=current_data['categories'],
            member_spending=current_data['member_spending'],
            daily_totals=current_data['daily_totals'],
        ),
        prior=schemas.StatsPriorData(
            income=prior_data['income'],
            expenses=prior_data['expenses'],
            savings=prior_data['savings'],
            savings_rate=prior_data['savings_rate'],
        ),
        trends=trends,
    )
