"""
Integration tests for /api/ai/* endpoints using FastAPI TestClient.
Auth, DB, and ai_service are all mocked — no real LLM or PostgreSQL needed.

Runs in the Docker test environment (docker-compose.test.yml) where all
backend requirements are installed.
"""
import io
import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth, models
from app.database import get_db
from app.routers.ai import router

# ── Test app helpers ───────────────────────────────────────────────────────────

FAMILY_ID = uuid.uuid4()
NARRATIVE_ID = uuid.uuid4()


def _mock_user():
    u = MagicMock(spec=models.User)
    u.family_id = FAMILY_ID
    u.id = uuid.uuid4()
    return u


def _mock_db(prefs=None, categories=None, narrative=None):
    """
    Build a mock SQLAlchemy Session.
    prefs=None → no FamilyPreference row → all AI features enabled by default.
    """
    db = MagicMock()

    def query_dispatch(model):
        q = MagicMock()
        if model is models.FamilyPreference:
            q.filter.return_value.first.return_value = prefs
        elif model is models.Category:
            cats = categories or []
            q.filter.return_value.all.return_value = cats
            q.filter.return_value.filter.return_value.all.return_value = cats
        elif model is models.AINarrative:
            chain = q.filter.return_value
            chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            chain.order_by.return_value.limit.return_value.all.return_value = []
            # dismiss uses single .filter(id, family_id).first() — set on chain directly
            chain.first.return_value = narrative
            # narratives GET uses .filter().filter().first() too — keep both paths
            chain.filter.return_value.first.return_value = narrative
        else:
            # Transaction and other models — return empty iterables
            q.filter.return_value.all.return_value = []
            q.filter.return_value.filter.return_value.all.return_value = []
        return q

    db.query.side_effect = query_dispatch
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


def _build_client(db=None):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[auth.get_current_user] = lambda: _mock_user()
    app.dependency_overrides[get_db] = lambda: (db if db is not None else _mock_db())
    return TestClient(app, raise_server_exceptions=False)


# Shared client using default mock db (no prefs → all features on)
client = _build_client()


# ── /ai/status ─────────────────────────────────────────────────────────────────

class TestAIStatus:
    def test_returns_200(self):
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.get("/api/ai/status")
        assert r.status_code == 200

    def test_available_true_when_llm_up(self):
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.get("/api/ai/status")
        assert r.json()["ai_service_available"] is True

    def test_available_false_when_llm_down(self):
        with patch("app.services.ai_service.is_available", return_value=False):
            r = client.get("/api/ai/status")
        assert r.json()["ai_service_available"] is False

    def test_all_features_enabled_when_no_prefs_row(self):
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.get("/api/ai/status")
        data = r.json()
        assert data["ai_categorization_enabled"] is True
        assert data["ai_receipt_ocr_enabled"] is True
        assert data["ai_voice_entry_enabled"] is True
        assert data["ai_statement_upload_enabled"] is True

    def test_feature_flag_respected_when_prefs_row_exists(self):
        prefs = MagicMock(spec=models.FamilyPreference)
        prefs.ai_categorization_enabled = False
        prefs.ai_monthly_narrative_enabled = True
        prefs.ai_weekly_digest_enabled = True
        prefs.ai_receipt_ocr_enabled = True
        prefs.ai_voice_entry_enabled = True
        prefs.ai_statement_upload_enabled = True
        c = _build_client(db=_mock_db(prefs=prefs))
        with patch("app.services.ai_service.is_available", return_value=True):
            r = c.get("/api/ai/status")
        assert r.json()["ai_categorization_enabled"] is False
        assert r.json()["ai_receipt_ocr_enabled"] is True


# ── /ai/categorize ────────────────────────────────────────────────────────────

class TestCategorize:
    def _post(self, description="SWIGGY ORDER 9845", db=None):
        c = _build_client(db=db) if db else client
        with patch("app.services.ai_service.is_available", return_value=True):
            return c.post("/api/ai/categorize", json={"description": description})

    def test_503_when_llm_down(self):
        with patch("app.services.ai_service.is_available", return_value=False):
            r = client.post("/api/ai/categorize", json={"description": "SWIGGY ORDER"})
        assert r.status_code == 503

    def test_422_when_categorize_returns_none(self):
        db = _mock_db(categories=[])
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.categorize_transaction", return_value=None):
            r = _build_client(db=db).post("/api/ai/categorize", json={"description": "SWIGGY"})
        assert r.status_code == 422

    def test_200_with_valid_category(self):
        cat_id = uuid.uuid4()
        mock_cat = MagicMock(spec=models.Category)
        mock_cat.name = "Dining"
        mock_cat.id = cat_id
        db = _mock_db(categories=[mock_cat])
        result = {"category": "Dining", "confidence": "high"}
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.categorize_transaction", return_value=result):
            r = _build_client(db=db).post("/api/ai/categorize", json={"description": "SWIGGY ORDER"})
        assert r.status_code == 200
        assert r.json()["category"] == "Dining"
        assert r.json()["confidence"] == "high"

    def test_403_when_feature_disabled(self):
        prefs = MagicMock(spec=models.FamilyPreference)
        prefs.ai_categorization_enabled = False
        db = _mock_db(prefs=prefs)
        with patch("app.services.ai_service.is_available", return_value=True):
            r = _build_client(db=db).post("/api/ai/categorize", json={"description": "SWIGGY"})
        assert r.status_code == 403


# ── /ai/parse-receipt ─────────────────────────────────────────────────────────

class TestParseReceipt:
    def _post(self, content=b"fake-image", content_type="image/jpeg", db=None):
        c = _build_client(db=db) if db else client
        with patch("app.services.ai_service.is_available", return_value=True):
            return c.post(
                "/api/ai/parse-receipt",
                files={"image": ("receipt.jpg", io.BytesIO(content), content_type)},
            )

    def test_400_wrong_content_type(self):
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.post(
                "/api/ai/parse-receipt",
                files={"image": ("doc.pdf", io.BytesIO(b"data"), "application/pdf")},
            )
        assert r.status_code == 400

    def test_413_file_too_large(self):
        big = b"x" * (11 * 1024 * 1024)  # 11 MB > 10 MB limit
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.post(
                "/api/ai/parse-receipt",
                files={"image": ("large.jpg", io.BytesIO(big), "image/jpeg")},
            )
        assert r.status_code == 413

    def test_503_when_llm_down(self):
        with patch("app.services.ai_service.is_available", return_value=False):
            r = client.post(
                "/api/ai/parse-receipt",
                files={"image": ("r.jpg", io.BytesIO(b"data"), "image/jpeg")},
            )
        assert r.status_code == 503

    def test_422_when_parse_returns_none(self):
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.parse_receipt", return_value=None):
            r = client.post(
                "/api/ai/parse-receipt",
                files={"image": ("r.jpg", io.BytesIO(b"data"), "image/jpeg")},
            )
        assert r.status_code == 422

    def test_200_on_successful_parse(self):
        result = {"is_receipt": True, "merchant": "Starbucks", "amount": 12.5,
                  "currency": "USD", "date": "2026-04-10", "category_hint": "Dining"}
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.parse_receipt", return_value=result):
            r = client.post(
                "/api/ai/parse-receipt",
                files={"image": ("r.jpg", io.BytesIO(b"data"), "image/jpeg")},
            )
        assert r.status_code == 200
        assert r.json()["merchant"] == "Starbucks"
        assert float(r.json()["amount"]) == 12.5

    def test_accepts_png_and_webp(self):
        result = {"is_receipt": True, "merchant": "Shop", "amount": 5.0,
                  "currency": "GBP", "date": None, "category_hint": None}
        for ct in ("image/png", "image/webp"):
            with patch("app.services.ai_service.is_available", return_value=True), \
                 patch("app.services.ai_service.parse_receipt", return_value=result):
                r = client.post(
                    "/api/ai/parse-receipt",
                    files={"image": ("r", io.BytesIO(b"data"), ct)},
                )
            assert r.status_code == 200, f"Expected 200 for {ct}"


# ── /ai/parse-voice ────────────────────────────────────────────────────────────

class TestParseVoice:
    def test_400_wrong_content_type(self):
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.post(
                "/api/ai/parse-voice",
                files={"audio": ("clip.mp3", io.BytesIO(b"data"), "audio/mpeg3")},
            )
        assert r.status_code == 400

    def test_413_file_too_large(self):
        big = b"x" * (26 * 1024 * 1024)  # 26 MB > 25 MB limit
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.post(
                "/api/ai/parse-voice",
                files={"audio": ("clip.webm", io.BytesIO(big), "audio/webm")},
            )
        assert r.status_code == 413

    def test_503_when_llm_down(self):
        with patch("app.services.ai_service.is_available", return_value=False):
            r = client.post(
                "/api/ai/parse-voice",
                files={"audio": ("clip.webm", io.BytesIO(b"data"), "audio/webm")},
            )
        assert r.status_code == 503

    def test_422_when_parse_returns_none(self):
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.parse_voice", return_value=None):
            r = client.post(
                "/api/ai/parse-voice",
                files={"audio": ("clip.webm", io.BytesIO(b"data"), "audio/webm")},
            )
        assert r.status_code == 422

    def test_200_on_successful_parse(self):
        result = {"is_transaction": True, "amount": 45.0, "currency": "GBP",
                  "description": "Tesco", "category_hint": "Groceries"}
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.parse_voice", return_value=result):
            r = client.post(
                "/api/ai/parse-voice",
                files={"audio": ("clip.webm", io.BytesIO(b"data"), "audio/webm")},
            )
        assert r.status_code == 200
        assert float(r.json()["amount"]) == 45.0
        assert r.json()["description"] == "Tesco"

    def test_accepts_ogg_mp4_wav(self):
        result = {"is_transaction": True, "amount": 10.0, "currency": "USD",
                  "description": "Test", "category_hint": None}
        for ct in ("audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"):
            with patch("app.services.ai_service.is_available", return_value=True), \
                 patch("app.services.ai_service.parse_voice", return_value=result):
                r = client.post(
                    "/api/ai/parse-voice",
                    files={"audio": ("clip", io.BytesIO(b"data"), ct)},
                )
            assert r.status_code == 200, f"Expected 200 for {ct}"


# ── /ai/parse-statement ───────────────────────────────────────────────────────

class TestParseStatement:
    def test_400_wrong_content_type(self):
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.post(
                "/api/ai/parse-statement",
                files={"file": ("stmt.txt", io.BytesIO(b"data"), "text/plain")},
            )
        assert r.status_code == 400

    def test_400_invalid_account_type(self):
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.post(
                "/api/ai/parse-statement?account_type=SAVINGS",
                files={"file": ("stmt.pdf", io.BytesIO(b"data"), "application/pdf")},
            )
        assert r.status_code == 400

    def test_413_file_too_large(self):
        big = b"x" * (21 * 1024 * 1024)  # 21 MB > 20 MB limit
        with patch("app.services.ai_service.is_available", return_value=True):
            r = client.post(
                "/api/ai/parse-statement",
                files={"file": ("stmt.pdf", io.BytesIO(big), "application/pdf")},
            )
        assert r.status_code == 413

    def test_503_when_llm_down(self):
        with patch("app.services.ai_service.is_available", return_value=False):
            r = client.post(
                "/api/ai/parse-statement",
                files={"file": ("stmt.pdf", io.BytesIO(b"data"), "application/pdf")},
            )
        assert r.status_code == 503

    def test_422_when_parse_returns_none(self):
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.parse_statement", return_value=None):
            r = client.post(
                "/api/ai/parse-statement",
                files={"file": ("stmt.pdf", io.BytesIO(b"data"), "application/pdf")},
            )
        assert r.status_code == 422

    def test_200_returns_transactions(self):
        rows = [
            {"date": "2026-04-01", "description": "Tesco", "amount": 45.0},
            {"date": "2026-04-02", "description": "Costa", "amount": 4.5},
        ]
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.parse_statement", return_value=rows), \
             patch("app.services.ai_service.categorize_transaction", return_value=None):
            r = client.post(
                "/api/ai/parse-statement",
                files={"file": ("stmt.pdf", io.BytesIO(b"data"), "application/pdf")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["raw_count"] == 2
        assert len(data["transactions"]) == 2
        assert data["transactions"][0]["description"] == "Tesco"

    def test_accepts_credit_card_account_type(self):
        rows = [{"date": "2026-04-01", "description": "Amazon", "amount": 99.0}]
        with patch("app.services.ai_service.is_available", return_value=True), \
             patch("app.services.ai_service.parse_statement", return_value=rows), \
             patch("app.services.ai_service.categorize_transaction", return_value=None):
            r = client.post(
                "/api/ai/parse-statement?account_type=CREDIT_CARD",
                files={"file": ("stmt.jpg", io.BytesIO(b"data"), "image/jpeg")},
            )
        assert r.status_code == 200


# ── /ai/narratives ─────────────────────────────────────────────────────────────

class TestNarratives:
    def test_get_returns_empty_list(self):
        r = client.get("/api/ai/narratives")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_returns_narratives(self):
        n = MagicMock(spec=models.AINarrative)
        n.id = NARRATIVE_ID
        n.family_id = FAMILY_ID
        n.narrative_type = "MONTHLY"
        n.period_label = "March 2026"
        n.content = "Great savings month!"
        n.generated_at = datetime.utcnow()
        n.dismissed_at = None
        db = _mock_db(narrative=n)

        # Override to return list on the narratives query
        def query_dispatch_with_list(model):
            q = MagicMock()
            if model is models.FamilyPreference:
                q.filter.return_value.first.return_value = None
            elif model is models.AINarrative:
                chain = q.filter.return_value
                chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [n]
                chain.order_by.return_value.limit.return_value.all.return_value = [n]
                chain.filter.return_value.first.return_value = n
            return q

        db.query.side_effect = query_dispatch_with_list
        c = _build_client(db=db)
        r = c.get("/api/ai/narratives")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_dismiss_returns_404_when_not_found(self):
        db = _mock_db(narrative=None)
        c = _build_client(db=db)
        r = c.post(f"/api/ai/narratives/{NARRATIVE_ID}/dismiss")
        assert r.status_code == 404

    def test_dismiss_returns_204_on_success(self):
        n = MagicMock(spec=models.AINarrative)
        n.family_id = FAMILY_ID
        n.dismissed_at = None
        db = _mock_db(narrative=n)

        def query_dispatch_dismiss(model):
            q = MagicMock()
            if model is models.FamilyPreference:
                q.filter.return_value.first.return_value = None
            elif model is models.AINarrative:
                q.filter.return_value.filter.return_value.first.return_value = n
            return q

        db.query.side_effect = query_dispatch_dismiss
        c = _build_client(db=db)
        r = c.post(f"/api/ai/narratives/{NARRATIVE_ID}/dismiss")
        assert r.status_code == 204
