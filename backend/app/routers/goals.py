from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from app import models, schemas
from app.database import get_db
from app.auth import get_current_user

router = APIRouter(prefix="/goals", tags=["goals"])


def _get_family_goal(db: Session, goal_id: UUID, family_id: UUID) -> models.Goal:
    goal = db.query(models.Goal).filter(
        models.Goal.id == goal_id,
        models.Goal.family_id == family_id,
        models.Goal.archived_at.is_(None),
    ).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


def _compute_progress(db: Session, goal: models.Goal) -> schemas.GoalProgress:
    """
    Compute current progress for a goal.

    - If linked_account_id is set: use the live account balance (auto-tracked).
    - Otherwise: use goal.current_amount which is updated by manual contributions.
    """
    if goal.linked_account_id:
        from app.financial_logic import FinancialEngine
        current_amount = FinancialEngine.calculate_account_balance(db, str(goal.linked_account_id))
    else:
        current_amount = goal.current_amount or Decimal("0")

    target = goal.target_amount
    percent = float(current_amount / target * 100) if target > 0 else 0.0
    percent = min(percent, 100.0)

    months_remaining = None
    days_remaining = None
    monthly_needed = None
    if goal.target_date:
        today = date.today()
        days_remaining = (goal.target_date - today).days
        delta_months = (goal.target_date.year - today.year) * 12 + (goal.target_date.month - today.month)
        months_remaining = max(delta_months, 0)
        remaining = target - current_amount
        if months_remaining > 0 and remaining > 0:
            monthly_needed = remaining / months_remaining

    return schemas.GoalProgress(
        goal_id=goal.id,
        name=goal.name,
        type=goal.type,
        target_amount=target,
        current_amount=current_amount,
        currency=goal.currency,
        percent=round(percent, 1),
        target_date=goal.target_date,
        months_remaining=months_remaining,
        days_remaining=days_remaining,
        monthly_needed=monthly_needed,
    )


@router.get("", response_model=List[schemas.GoalResponse])
def list_goals(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Goal).filter(models.Goal.family_id == current_user.family_id)
    if not include_archived:
        q = q.filter(models.Goal.archived_at.is_(None))
    return q.order_by(models.Goal.created_at.desc()).all()


@router.post("", response_model=schemas.GoalResponse, status_code=201)
def create_goal(
    payload: schemas.GoalCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = models.Goal(
        family_id=current_user.family_id,
        current_amount=Decimal("0"),
        **payload.model_dump(),
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/{goal_id}", response_model=schemas.GoalResponse)
def get_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_family_goal(db, goal_id, current_user.family_id)


@router.put("/{goal_id}", response_model=schemas.GoalResponse)
def update_goal(
    goal_id: UUID,
    payload: schemas.GoalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = _get_family_goal(db, goal_id, current_user.family_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
def archive_goal(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = _get_family_goal(db, goal_id, current_user.family_id)
    goal.archived_at = datetime.utcnow()
    db.commit()


@router.get("/{goal_id}/progress", response_model=schemas.GoalProgress)
def goal_progress(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = _get_family_goal(db, goal_id, current_user.family_id)
    return _compute_progress(db, goal)


@router.post("/{goal_id}/contribute", response_model=schemas.GoalContributionResponse, status_code=201)
def add_contribution(
    goal_id: UUID,
    payload: schemas.GoalContributeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Add a manual contribution toward a goal and update its running total."""
    goal = _get_family_goal(db, goal_id, current_user.family_id)

    contribution = models.GoalContribution(
        goal_id=goal.id,
        amount=payload.amount,
        note=payload.note,
        contributed_at=payload.contributed_at or date.today(),
    )
    db.add(contribution)

    # Update denormalized running total
    goal.current_amount = (goal.current_amount or Decimal("0")) + payload.amount
    goal.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(contribution)
    return contribution


@router.get("/{goal_id}/contributions", response_model=List[schemas.GoalContributionResponse])
def list_contributions(
    goal_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    goal = _get_family_goal(db, goal_id, current_user.family_id)
    return (
        db.query(models.GoalContribution)
        .filter(models.GoalContribution.goal_id == goal.id)
        .order_by(models.GoalContribution.contributed_at.desc())
        .all()
    )
