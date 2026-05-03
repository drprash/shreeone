"""
Session-level conftest: ensure all ALTER TABLE migrations have been applied
to the test database before any tests run.

This mirrors the `ensure_performance_indexes()` call in main.py, which runs
when the FastAPI app starts but is NOT invoked when tests create DB sessions
directly (without TestClient).
"""
import pytest
from app.database import engine, Base
from sqlalchemy import text


def _apply_schema_migrations():
    """Run all idempotent ALTER TABLE and CREATE TABLE IF NOT EXISTS statements."""
    statements = [
        "ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS country_code VARCHAR(2)",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS current_value NUMERIC(15,2)",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_valued_at TIMESTAMP",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS show_net_worth_by_country BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS show_member_spending BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_categorization_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_monthly_narrative_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_weekly_digest_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_receipt_ocr_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_voice_entry_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_statement_upload_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_provider VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_model_override VARCHAR(100) DEFAULT NULL",
        "ALTER TABLE family_preferences ADD COLUMN IF NOT EXISTS ai_services_enabled BOOLEAN NOT NULL DEFAULT FALSE",
        """CREATE TABLE IF NOT EXISTS ai_narratives (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            family_id UUID NOT NULL REFERENCES families(id),
            narrative_type VARCHAR(10) NOT NULL,
            period_label VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            generated_at TIMESTAMP DEFAULT NOW(),
            dismissed_at TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS net_worth_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            family_id UUID NOT NULL REFERENCES families(id),
            snapshot_date DATE NOT NULL,
            total_net_worth NUMERIC(15,2) NOT NULL,
            breakdown_json TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_family_snapshot_date UNIQUE (family_id, snapshot_date)
        )""",
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
        """CREATE TABLE IF NOT EXISTS remittances (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            family_id UUID NOT NULL REFERENCES families(id),
            sent_date DATE NOT NULL,
            amount_sent NUMERIC(15,2) NOT NULL,
            currency_sent VARCHAR(3) NOT NULL,
            amount_received_inr NUMERIC(15,2),
            exchange_rate_achieved NUMERIC(10,6),
            provider VARCHAR(100),
            recipient_note TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]

    with engine.begin() as conn:
        # Ensure tables exist first
        Base.metadata.create_all(bind=conn)
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print(f"[conftest] Warning: {e}")


# Run once per test session before any tests collect/run.
_apply_schema_migrations()
