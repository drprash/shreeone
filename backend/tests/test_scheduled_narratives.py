"""
Tests for the scheduled AI narrative tasks (weekly digest / monthly narrative / goal).

Bug: the scheduled tasks in main.py called ai_service.is_available() and the
generators WITHOUT family_id/db, so provider resolution fell back to the server
env default (local Ollama). On deployments where the family selected a cloud
provider in Settings (prefs.ai_provider) and Ollama is not running, manual
generation worked but every scheduled run logged "AI service unavailable —
skipping" and produced nothing.

The tasks must:
  1. Check availability per family (family_id + db), not globally.
  2. Pass family_id + db to the generators so the family's provider is used.
  3. Skip periods that already have an undismissed narrative (parity with the
     manual /ai/narratives/generate endpoint), so a manual run followed by the
     cron run does not create duplicates.
"""
import calendar
import uuid
from datetime import datetime, timedelta

import pytest

from app import models
from app.database import Base, SessionLocal, engine
from app.services import ai_service


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        _cleanup(db)
        yield db
    finally:
        db.rollback()
        _cleanup(db)
        db.close()


def _cleanup(db):
    db.query(models.AINarrative).delete()
    db.query(models.GoalContribution).delete()
    db.query(models.Goal).delete()
    db.query(models.NetWorthSnapshot).delete()
    db.query(models.FamilyPreference).delete()
    db.query(models.Transaction).delete()
    db.query(models.Account).delete()
    db.query(models.User).delete()
    db.query(models.Family).delete()
    db.commit()


def _make_family_with_cloud_provider(db):
    family = models.Family(
        id=uuid.uuid4(), name="Cloud Family", base_currency="USD",
        privacy_level=models.PrivacyLevel.FAMILY,
    )
    db.add(family)
    db.flush()
    prefs = models.FamilyPreference(
        family_id=family.id,
        ai_services_enabled=True,
        ai_provider="anthropic",
    )
    db.add(prefs)
    db.commit()
    return family


def _patch_ai(monkeypatch, calls):
    """Simulate: env-default backend DOWN, family-scoped backend UP."""

    def fake_is_available(family_id=None, db=None):
        return family_id is not None

    def fake_weekly(summary, family_id=None, db=None):
        calls.append(("weekly", family_id, db))
        return "weekly digest text"

    def fake_monthly(summary, family_id=None, db=None):
        calls.append(("monthly", family_id, db))
        return "monthly narrative text"

    def fake_period_summary(db, family, start_date, end_date):
        return {"total_expenses": 123.0, "total_income": 0.0, "top_categories": []}

    monkeypatch.setattr(ai_service, "is_available", fake_is_available)
    monkeypatch.setattr(ai_service, "generate_weekly_digest", fake_weekly)
    monkeypatch.setattr(ai_service, "generate_monthly_narrative", fake_monthly)
    monkeypatch.setattr(ai_service, "build_period_summary", fake_period_summary)


def _weekly_period_label():
    end_date = datetime.utcnow().date() - timedelta(days=1)
    return f"Week of {end_date.strftime('%b %d')}"


def _monthly_period_label():
    now = datetime.utcnow()
    prev_month = now.month - 1 or 12
    prev_year = now.year if now.month > 1 else now.year - 1
    return f"{calendar.month_name[prev_month]} {prev_year}"


# ─── weekly digest ────────────────────────────────────────────────────────────

def test_weekly_task_generates_when_only_family_provider_available(db_session, monkeypatch):
    family = _make_family_with_cloud_provider(db_session)
    calls = []
    _patch_ai(monkeypatch, calls)

    from app.main import generate_weekly_digests_task
    generate_weekly_digests_task()

    narratives = db_session.query(models.AINarrative).filter(
        models.AINarrative.family_id == family.id,
        models.AINarrative.narrative_type == "WEEKLY",
    ).all()
    assert len(narratives) == 1, (
        "Weekly task skipped generation: global is_available() short-circuit "
        "instead of per-family availability check"
    )


def test_weekly_task_passes_family_context_to_generator(db_session, monkeypatch):
    family = _make_family_with_cloud_provider(db_session)
    calls = []
    _patch_ai(monkeypatch, calls)

    from app.main import generate_weekly_digests_task
    generate_weekly_digests_task()

    weekly_calls = [c for c in calls if c[0] == "weekly"]
    assert weekly_calls, "generate_weekly_digest was never called"
    _, family_id, db_arg = weekly_calls[0]
    assert family_id == family.id, "generator not given family_id — wrong provider would be used"
    assert db_arg is not None, "generator not given db session — family provider cannot resolve"


def test_weekly_task_skips_existing_period_narrative(db_session, monkeypatch):
    family = _make_family_with_cloud_provider(db_session)
    db_session.add(models.AINarrative(
        family_id=family.id,
        narrative_type="WEEKLY",
        period_label=_weekly_period_label(),
        content="already generated manually",
    ))
    db_session.commit()
    calls = []
    _patch_ai(monkeypatch, calls)

    from app.main import generate_weekly_digests_task
    generate_weekly_digests_task()

    count = db_session.query(models.AINarrative).filter(
        models.AINarrative.family_id == family.id,
        models.AINarrative.narrative_type == "WEEKLY",
    ).count()
    assert count == 1, "scheduled run duplicated a narrative already generated manually"


# ─── monthly narrative ────────────────────────────────────────────────────────

def test_monthly_task_generates_when_only_family_provider_available(db_session, monkeypatch):
    family = _make_family_with_cloud_provider(db_session)
    calls = []
    _patch_ai(monkeypatch, calls)

    from app.main import generate_monthly_narratives_task
    generate_monthly_narratives_task()

    narratives = db_session.query(models.AINarrative).filter(
        models.AINarrative.family_id == family.id,
        models.AINarrative.narrative_type == "MONTHLY",
    ).all()
    assert len(narratives) == 1, (
        "Monthly task skipped generation: global is_available() short-circuit "
        "instead of per-family availability check"
    )


def test_monthly_task_passes_family_context_to_generator(db_session, monkeypatch):
    family = _make_family_with_cloud_provider(db_session)
    calls = []
    _patch_ai(monkeypatch, calls)

    from app.main import generate_monthly_narratives_task
    generate_monthly_narratives_task()

    monthly_calls = [c for c in calls if c[0] == "monthly"]
    assert monthly_calls, "generate_monthly_narrative was never called"
    _, family_id, db_arg = monthly_calls[0]
    assert family_id == family.id
    assert db_arg is not None


def test_monthly_task_skips_existing_period_narrative(db_session, monkeypatch):
    family = _make_family_with_cloud_provider(db_session)
    db_session.add(models.AINarrative(
        family_id=family.id,
        narrative_type="MONTHLY",
        period_label=_monthly_period_label(),
        content="already generated manually",
    ))
    db_session.commit()
    calls = []
    _patch_ai(monkeypatch, calls)

    from app.main import generate_monthly_narratives_task
    generate_monthly_narratives_task()

    count = db_session.query(models.AINarrative).filter(
        models.AINarrative.family_id == family.id,
        models.AINarrative.narrative_type == "MONTHLY",
    ).count()
    assert count == 1, "scheduled run duplicated a narrative already generated manually"


# ─── goal narratives ──────────────────────────────────────────────────────────

def test_goal_task_passes_family_context(db_session, monkeypatch):
    family = _make_family_with_cloud_provider(db_session)
    db_session.add(models.Goal(
        family_id=family.id,
        name="Emergency Fund",
        type=models.GoalType.SAVINGS_TARGET,
        target_amount=10000,
        currency="USD",
    ))
    db_session.commit()
    calls = []
    _patch_ai(monkeypatch, calls)

    from app.main import generate_goal_narratives_task
    generate_goal_narratives_task()

    goal_calls = [c for c in calls if c[0] == "monthly"]  # goal task reuses monthly generator
    assert goal_calls, (
        "Goal task skipped generation: global is_available() short-circuit "
        "instead of per-family availability check"
    )
    _, family_id, db_arg = goal_calls[0]
    assert family_id == family.id
    assert db_arg is not None
