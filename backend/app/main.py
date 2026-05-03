from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import engine, Base, SessionLocal
from app.config import settings
from app.routers import auth, accounts, transactions, categories, dashboard, admin, sync, backup
from app.routers import settings as settings_router
from app.routers import ai as ai_router
from app.routers import goals as goals_router
from app.recurring_processor import RecurringPaymentProcessor
from app.exchange_rate_service import fetch_all_family_rates
from app.services import ai_service
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime


def build_allowed_origins(frontend_url_value: str) -> list[str]:
    origins = [item.strip() for item in frontend_url_value.split(",") if item.strip()]
    allow_origins: list[str] = []

    for origin in origins:
        if origin not in allow_origins:
            allow_origins.append(origin)

        if "localhost" in origin:
            mirror_origin = origin.replace("localhost", "127.0.0.1")
            if mirror_origin not in allow_origins:
                allow_origins.append(mirror_origin)
        elif "127.0.0.1" in origin:
            mirror_origin = origin.replace("127.0.0.1", "localhost")
            if mirror_origin not in allow_origins:
                allow_origins.append(mirror_origin)

    return allow_origins

# Create tables
Base.metadata.create_all(bind=engine)

# Model-driven schema creation + optional index ensure.
def ensure_performance_indexes():
    """Create hot-path indexes for fresh/reinitialized databases."""
    with engine.begin() as connection:
        performance_indexes = [
            "ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS country_code VARCHAR(2)",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS show_net_worth_by_country BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS show_member_spending BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_categorization_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_monthly_narrative_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_weekly_digest_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_receipt_ocr_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_voice_entry_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_statement_upload_enabled BOOLEAN NOT NULL DEFAULT TRUE",
            # ensure ai_narratives exists if create_all ran before this model was added
            """CREATE TABLE IF NOT EXISTS ai_narratives (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                family_id UUID NOT NULL REFERENCES families(id),
                narrative_type VARCHAR(10) NOT NULL,
                period_label VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT NOW(),
                dismissed_at TIMESTAMP
            )""",
            "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS current_value NUMERIC(15,2)",
            "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_valued_at TIMESTAMP",
            """CREATE TABLE IF NOT EXISTS net_worth_snapshots (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                family_id UUID NOT NULL REFERENCES families(id),
                snapshot_date DATE NOT NULL,
                total_net_worth NUMERIC(15,2) NOT NULL,
                breakdown_json TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_family_snapshot_date UNIQUE (family_id, snapshot_date)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_snapshots_family_date ON net_worth_snapshots (family_id, snapshot_date DESC)",
            """CREATE TABLE IF NOT EXISTS goals (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                family_id UUID NOT NULL REFERENCES families(id),
                name VARCHAR(200) NOT NULL,
                type VARCHAR(30) NOT NULL,
                target_amount NUMERIC(15,2) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                target_date DATE,
                linked_account_id UUID REFERENCES accounts(id),
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                archived_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS idx_accounts_family_deleted ON accounts (family_id, deleted_at)",
            "CREATE INDEX IF NOT EXISTS idx_categories_family_deleted ON categories (family_id, deleted_at)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_account_deleted_date ON transactions (account_id, deleted_at, transaction_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_creator_deleted_date ON transactions (created_by_user_id, deleted_at, transaction_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_type_deleted_date ON transactions (type, deleted_at, transaction_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_recurring_active_next_due ON recurring_payments (is_active, next_due_date)",
            "CREATE INDEX IF NOT EXISTS idx_accounts_updated_at ON accounts (updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_categories_updated_at ON categories (updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_updated_at ON transactions (updated_at)",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_provider VARCHAR(20) DEFAULT NULL",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_model_override VARCHAR(100) DEFAULT NULL",
            "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_services_enabled BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE goals ADD COLUMN IF NOT EXISTS current_amount NUMERIC(15,2) NOT NULL DEFAULT 0",
            """CREATE TABLE IF NOT EXISTS goal_contributions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
                amount NUMERIC(15,2) NOT NULL,
                note TEXT,
                contributed_at DATE NOT NULL DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS idx_goal_contributions_goal ON goal_contributions (goal_id, contributed_at DESC)",
        ]

        for statement in performance_indexes:
            try:
                connection.execute(text(statement))
            except Exception as e:
                print(f"Warning: Could not create performance index: {e}")

ensure_performance_indexes()

# ============ Recurring Payment Scheduler ============
scheduler = BackgroundScheduler()

def process_recurring_payments_task():
    """Background task to process due recurring payments"""
    db = SessionLocal()
    try:
        count = RecurringPaymentProcessor.process_all_due_recurring_payments(db)
        if count > 0:
            print(f"[{datetime.utcnow()}] Successfully processed {count} recurring payment(s)")
    except Exception as e:
        print(f"[{datetime.utcnow()}] Error processing recurring payments: {str(e)}")
    finally:
        db.close()


def prune_tokens_task():
    """Background task to prune expired refresh tokens and WebAuthn challenges"""
    from app import crud
    db = SessionLocal()
    try:
        n1 = crud.prune_expired_refresh_tokens(db)
        n2 = crud.prune_expired_webauthn_challenges(db)
        if n1 or n2:
            print(f"[{datetime.utcnow()}] Pruned {n1} refresh token(s), {n2} WebAuthn challenge(s)")
    except Exception as e:
        print(f"[{datetime.utcnow()}] Error pruning tokens: {str(e)}")
    finally:
        db.close()

def _build_period_summary(db, family, start_date, end_date):
    """
    Query transactions for a family within [start_date, end_date] and return a summary dict.
    Returns keys: total_income, total_expenses, net_savings, savings_rate, top_categories.
    Amounts are in the family's base currency (amount_in_base_currency column).
    Returns None if no transactions found.
    """
    from app import models as app_models
    from sqlalchemy import func
    from decimal import Decimal

    # Collect account IDs for this family
    account_ids = [
        a.id for a in db.query(app_models.Account.id).filter(
            app_models.Account.family_id == family.id,
            app_models.Account.deleted_at.is_(None),
        ).all()
    ]
    if not account_ids:
        return None

    base_q = db.query(app_models.Transaction).filter(
        app_models.Transaction.account_id.in_(account_ids),
        app_models.Transaction.deleted_at.is_(None),
        app_models.Transaction.transaction_date >= start_date,
        app_models.Transaction.transaction_date <= end_date,
    )

    total_income = Decimal("0")
    total_expenses = Decimal("0")
    for tx in base_q.all():
        base_amt = tx.amount_in_base_currency or Decimal("0")
        if tx.type == app_models.TransactionType.INCOME:
            total_income += base_amt
        elif tx.type == app_models.TransactionType.EXPENSE:
            total_expenses += base_amt

    if total_income == 0 and total_expenses == 0:
        return None

    net_savings = total_income - total_expenses
    savings_rate = round(float(net_savings / total_income * 100), 1) if total_income else 0.0

    # Top categories by expense amount
    cat_rows = (
        base_q.filter(
            app_models.Transaction.type == app_models.TransactionType.EXPENSE,
            app_models.Transaction.category_id.is_not(None),
        )
        .with_entities(
            app_models.Transaction.category_id,
            func.sum(app_models.Transaction.amount_in_base_currency).label("total"),
        )
        .group_by(app_models.Transaction.category_id)
        .order_by(func.sum(app_models.Transaction.amount_in_base_currency).desc())
        .limit(5)
        .all()
    )

    cat_ids = [r.category_id for r in cat_rows]
    cat_map = {}
    if cat_ids:
        cats = db.query(app_models.Category).filter(
            app_models.Category.id.in_(cat_ids)
        ).all()
        cat_map = {c.id: c.name for c in cats}

    top_categories = [
        {"name": cat_map.get(r.category_id, "Other"), "amount": round(float(r.total), 2)}
        for r in cat_rows
    ]

    return {
        "total_income": round(float(total_income), 2),
        "total_expenses": round(float(total_expenses), 2),
        "net_savings": round(float(net_savings), 2),
        "savings_rate": savings_rate,
        "top_categories": top_categories,
    }


def record_net_worth_snapshot_task():
    """Daily at 03:00 — record a net worth snapshot for each family."""
    db = SessionLocal()
    try:
        from app import models as app_models
        from app.financial_logic import FinancialEngine
        import json
        from decimal import Decimal
        today = datetime.utcnow().date()

        families = db.query(app_models.Family).filter(
            app_models.Family.deleted_at.is_(None)
        ).all()

        recorded = 0
        for family in families:
            # Skip if already recorded today
            existing = db.query(app_models.NetWorthSnapshot).filter(
                app_models.NetWorthSnapshot.family_id == family.id,
                app_models.NetWorthSnapshot.snapshot_date == today,
            ).first()
            if existing:
                continue

            accounts = db.query(app_models.Account).filter(
                app_models.Account.family_id == family.id,
                app_models.Account.deleted_at.is_(None),
                app_models.Account.include_in_family_overview == True,
            ).all()

            base_currency = family.base_currency
            total_net_worth = Decimal("0")
            breakdown = {"cash": 0.0, "bank": 0.0, "investment": 0.0, "property": 0.0, "liability": 0.0}

            for account in accounts:
                if account.type in app_models.VALUATION_ACCOUNT_TYPES and account.current_value is not None:
                    balance = account.current_value
                elif account.type in app_models.LIABILITY_ACCOUNT_TYPES:
                    balance = FinancialEngine.calculate_account_balance(db, str(account.id))
                else:
                    balance = account.current_balance or Decimal("0")

                if account.currency != base_currency:
                    rate = FinancialEngine.get_exchange_rate(db, account.currency, base_currency, family_id=family.id)
                    balance_base = balance * rate
                else:
                    balance_base = balance

                if account.type in app_models.LIABILITY_ACCOUNT_TYPES:
                    breakdown["liability"] += float(balance_base)
                    total_net_worth -= balance_base
                elif account.type == app_models.AccountType.CASH:
                    breakdown["cash"] += float(balance_base)
                    total_net_worth += balance_base
                elif account.type == app_models.AccountType.BANK:
                    breakdown["bank"] += float(balance_base)
                    total_net_worth += balance_base
                elif account.type == app_models.AccountType.PROPERTY:
                    breakdown["property"] += float(balance_base)
                    total_net_worth += balance_base
                else:
                    breakdown["investment"] += float(balance_base)
                    total_net_worth += balance_base

            snapshot = app_models.NetWorthSnapshot(
                family_id=family.id,
                snapshot_date=today,
                total_net_worth=total_net_worth,
                breakdown_json=json.dumps(breakdown),
            )
            db.add(snapshot)
            recorded += 1

        db.commit()
        if recorded:
            print(f"[{datetime.utcnow()}] Recorded net worth snapshots for {recorded} family/families")
    except Exception as e:
        print(f"[{datetime.utcnow()}] Error recording net worth snapshots: {e}")
    finally:
        db.close()


def generate_goal_narratives_task():
    """Weekly on Monday 09:00 — AI goal recommendations for each family."""
    if not ai_service.is_available():
        print(f"[{datetime.utcnow()}] AI service unavailable — skipping goal narratives")
        return
    db = SessionLocal()
    try:
        from app import models as app_models
        families = db.query(app_models.Family).filter(
            app_models.Family.deleted_at.is_(None)
        ).all()
        generated = 0
        for family in families:
            goals = db.query(app_models.Goal).filter(
                app_models.Goal.family_id == family.id,
                app_models.Goal.archived_at.is_(None),
            ).all()
            if not goals:
                continue

            prefs = db.query(app_models.FamilyPreference).filter(
                app_models.FamilyPreference.family_id == family.id
            ).first()
            if prefs and not getattr(prefs, "ai_services_enabled", True):
                continue

            # Latest net worth snapshot
            snapshot = db.query(app_models.NetWorthSnapshot).filter(
                app_models.NetWorthSnapshot.family_id == family.id,
            ).order_by(app_models.NetWorthSnapshot.snapshot_date.desc()).first()

            from datetime import timedelta
            now = datetime.utcnow()
            start_3m = now.date() - timedelta(days=90)
            period_data = _build_period_summary(db, family, start_3m, now.date())

            goal_summaries = [
                {
                    "name": g.name,
                    "type": g.type.value,
                    "target_amount": float(g.target_amount),
                    "currency": g.currency,
                    "target_date": g.target_date.isoformat() if g.target_date else None,
                }
                for g in goals
            ]

            summary = {
                "family_name": family.name,
                "base_currency": family.base_currency,
                "goals": goal_summaries,
                "net_worth": float(snapshot.total_net_worth) if snapshot else None,
                "recent_financials": period_data,
            }

            prompt = (
                f"You are a financial advisor for {family.name}. "
                f"Here is their current financial snapshot and goals:\n{summary}\n"
                "Provide a brief, actionable recommendation (2-3 sentences) on which goal "
                "to prioritise this week and how to make progress toward it."
            )

            # Reuse generate_monthly_narrative with a custom prompt via ai_service
            content = ai_service.generate_monthly_narrative({"_raw_prompt": prompt, **summary})
            if content:
                narrative = app_models.AINarrative(
                    family_id=family.id,
                    narrative_type="GOAL",
                    period_label=f"Week of {now.strftime('%b %d')}",
                    content=content,
                )
                db.add(narrative)
                generated += 1

        db.commit()
        if generated:
            print(f"[{datetime.utcnow()}] Generated {generated} goal narrative(s)")
    except Exception as e:
        print(f"[{datetime.utcnow()}] Error generating goal narratives: {e}")
    finally:
        db.close()


def generate_monthly_narratives_task():
    """Generate AI monthly narrative for each family (runs 1st of month at 02:00)."""
    if not ai_service.is_available():
        print(f"[{datetime.utcnow()}] AI service unavailable — skipping monthly narratives")
        return
    db = SessionLocal()
    try:
        from app import models as app_models
        import calendar
        now = datetime.utcnow()
        if now.month == 1:
            prev_month, prev_year = 12, now.year - 1
        else:
            prev_month, prev_year = now.month - 1, now.year
        month_name = calendar.month_name[prev_month]
        period_label = f"{month_name} {prev_year}"

        from datetime import date
        start_date = date(prev_year, prev_month, 1)
        last_day = calendar.monthrange(prev_year, prev_month)[1]
        end_date = date(prev_year, prev_month, last_day)

        families = db.query(app_models.Family).filter(
            app_models.Family.deleted_at.is_(None)
        ).all()
        generated = 0
        for family in families:
            prefs = db.query(app_models.FamilyPreference).filter(
                app_models.FamilyPreference.family_id == family.id
            ).first()
            if prefs and (not getattr(prefs, "ai_services_enabled", True) or not getattr(prefs, "ai_monthly_narrative_enabled", True)):
                continue
            period_data = _build_period_summary(db, family, start_date, end_date)
            if period_data is None:
                continue  # no transactions — skip rather than generate empty narrative
            summary = {
                "month": period_label,
                "family_name": family.name,
                "base_currency": family.base_currency,
                **period_data,
            }
            content = ai_service.generate_monthly_narrative(summary)
            if content:
                narrative = app_models.AINarrative(
                    family_id=family.id,
                    narrative_type="MONTHLY",
                    period_label=period_label,
                    content=content,
                )
                db.add(narrative)
                generated += 1
        db.commit()
        if generated:
            print(f"[{datetime.utcnow()}] Generated {generated} monthly narrative(s)")
    except Exception as e:
        print(f"[{datetime.utcnow()}] Error generating monthly narratives: {e}")
    finally:
        db.close()


def generate_weekly_digests_task():
    """Generate AI weekly digest for each family (runs every Monday at 08:00)."""
    if not ai_service.is_available():
        print(f"[{datetime.utcnow()}] AI service unavailable — skipping weekly digests")
        return
    db = SessionLocal()
    try:
        from app import models as app_models
        from datetime import date, timedelta
        now = datetime.utcnow()
        # Digest covers the previous 7 days (Mon–Sun when run on Monday)
        end_date = now.date() - timedelta(days=1)
        start_date = end_date - timedelta(days=6)
        week_ending = end_date.strftime("%b %d")
        period_label = f"Week of {week_ending}"

        families = db.query(app_models.Family).filter(
            app_models.Family.deleted_at.is_(None)
        ).all()
        generated = 0
        for family in families:
            prefs = db.query(app_models.FamilyPreference).filter(
                app_models.FamilyPreference.family_id == family.id
            ).first()
            if prefs and (not getattr(prefs, "ai_services_enabled", True) or not getattr(prefs, "ai_weekly_digest_enabled", True)):
                continue
            period_data = _build_period_summary(db, family, start_date, end_date)
            if period_data is None:
                continue  # no transactions this week — skip
            summary = {
                "week_ending": week_ending,
                "family_name": family.name,
                "base_currency": family.base_currency,
                "total_spent": period_data["total_expenses"],
                "top_categories": period_data["top_categories"],
            }
            content = ai_service.generate_weekly_digest(summary)
            if content:
                narrative = app_models.AINarrative(
                    family_id=family.id,
                    narrative_type="WEEKLY",
                    period_label=period_label,
                    content=content,
                )
                db.add(narrative)
                generated += 1
        db.commit()
        if generated:
            print(f"[{datetime.utcnow()}] Generated {generated} weekly digest(s)")
    except Exception as e:
        print(f"[{datetime.utcnow()}] Error generating weekly digests: {e}")
    finally:
        db.close()


app = FastAPI(
    title=settings.app_name,
    description="Multi-user family financial management system",
    version="1.0.0"
)

allowed_origins = build_allowed_origins(settings.frontend_url)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(backup.router, prefix="/api")
app.include_router(ai_router.router, prefix="/api")
app.include_router(goals_router.router, prefix="/api")

# ============ Startup and Shutdown Events ============
@app.on_event("startup")
async def startup_event():
    """Register and start all background scheduled jobs, then run startup tasks."""
    try:
        # Daily at 00:00 — process any recurring payments that are due
        scheduler.add_job(
            process_recurring_payments_task,
            'cron',
            hour=0,
            minute=0,
            id='process_recurring_payments',
            name='Process Recurring Payments',
            replace_existing=True
        )
        # Daily at 01:00 — prune expired refresh tokens and WebAuthn challenges
        scheduler.add_job(
            prune_tokens_task,
            'cron',
            hour=1,
            minute=0,
            id='prune_tokens',
            name='Prune Expired Tokens',
            replace_existing=True
        )
        # Daily at 06:00 — fetch fresh exchange rates (ECB + FloatRates fallback)
        # and prune rate rows older than 14 days
        scheduler.add_job(
            fetch_all_family_rates,
            'cron',
            hour=6,
            minute=0,
            id='fetch_exchange_rates',
            name='Fetch Exchange Rates',
            replace_existing=True
        )
        # 1st of each month at 02:00 — AI monthly narrative
        scheduler.add_job(
            generate_monthly_narratives_task,
            'cron',
            day=1,
            hour=2,
            minute=0,
            id='ai_monthly_narratives',
            name='AI Monthly Narratives',
            replace_existing=True
        )
        # Every Monday at 08:00 — AI weekly digest
        scheduler.add_job(
            generate_weekly_digests_task,
            'cron',
            day_of_week='mon',
            hour=8,
            minute=0,
            id='ai_weekly_digests',
            name='AI Weekly Digests',
            replace_existing=True
        )
        # Daily at 03:00 — net worth snapshot
        scheduler.add_job(
            record_net_worth_snapshot_task,
            'cron',
            hour=3,
            minute=0,
            id='net_worth_snapshot',
            name='Net Worth Snapshot',
            replace_existing=True
        )
        # Every Monday at 09:00 — AI goal recommendations
        scheduler.add_job(
            generate_goal_narratives_task,
            'cron',
            day_of_week='mon',
            hour=9,
            minute=0,
            id='ai_goal_narratives',
            name='AI Goal Narratives',
            replace_existing=True
        )
        scheduler.start()
        print("✓ Background scheduler started (7 jobs registered)")

        # Run immediately on startup to catch up on anything missed if the server
        # was down at the scheduled run time.

        # Safety: double-processing recurring payments is prevented by
        # last_paid_date — payments already processed today are skipped.
        print("Processing any due recurring payments on startup...")
        process_recurring_payments_task()

        print("Fetching exchange rates on startup...")
        fetch_all_family_rates()
    except Exception as e:
        print(f"✗ Failed to start background scheduler: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop all background scheduled jobs on app shutdown."""
    if scheduler.running:
        scheduler.shutdown()
        print("✓ Background scheduler stopped")

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/")
def root():
    return {
        "message": "ShreeOne Family Finance API",
        "docs": "/docs",
        "health": "/api/health"
    }
