from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import engine, Base, SessionLocal
from app.config import settings
from app.routers import auth, accounts, transactions, categories, dashboard, admin, sync, backup
from app.routers import settings as settings_router
from app.recurring_processor import RecurringPaymentProcessor
from app.exchange_rate_service import fetch_all_family_rates
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
            "CREATE INDEX IF NOT EXISTS idx_accounts_family_deleted ON accounts (family_id, deleted_at)",
            "CREATE INDEX IF NOT EXISTS idx_categories_family_deleted ON categories (family_id, deleted_at)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_account_deleted_date ON transactions (account_id, deleted_at, transaction_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_creator_deleted_date ON transactions (created_by_user_id, deleted_at, transaction_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_type_deleted_date ON transactions (type, deleted_at, transaction_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_recurring_active_next_due ON recurring_payments (is_active, next_due_date)",
            "CREATE INDEX IF NOT EXISTS idx_accounts_updated_at ON accounts (updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_categories_updated_at ON categories (updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_updated_at ON transactions (updated_at)",
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
        scheduler.start()
        print("✓ Background scheduler started (3 jobs registered)")

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
