"""
Unit tests for ai_service.py — all LLM calls are mocked via httpx.

Run with: pytest backend/tests/test_ai_service.py -v
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services import ai_service


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_completion(content: str):
    """Build a mock httpx response for /completion."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"content": content}
    mock.raise_for_status = MagicMock()
    return mock


def _mock_chat(content: str):
    """Build a mock httpx response for /v1/chat/completions."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    mock.raise_for_status = MagicMock()
    return mock


def _mock_error():
    """Build a mock that raises an exception."""
    mock = MagicMock()
    mock.raise_for_status.side_effect = Exception("LLM unreachable")
    return mock


# ── is_available ───────────────────────────────────────────────────────────────

def test_is_available_returns_true_when_health_ok():
    mock = MagicMock()
    mock.status_code = 200
    with patch("httpx.get", return_value=mock):
        assert ai_service.is_available() is True


def test_is_available_returns_false_on_exception():
    with patch("httpx.get", side_effect=Exception("connection refused")):
        assert ai_service.is_available() is False


def test_is_available_returns_false_on_non_200():
    mock = MagicMock()
    mock.status_code = 503
    with patch("httpx.get", return_value=mock):
        assert ai_service.is_available() is False


# ── categorize_transaction ─────────────────────────────────────────────────────

def test_categorize_transaction_happy_path():
    payload = json.dumps({"category": "Dining", "confidence": "high"})
    with patch("httpx.post", return_value=_mock_chat(payload)):
        result = ai_service.categorize_transaction("SWIGGY ORDER 9845", ["Dining", "Groceries"])
    assert result == {"category": "Dining", "confidence": "high"}


def test_categorize_transaction_rejects_category_not_in_list():
    payload = json.dumps({"category": "Travel", "confidence": "high"})
    with patch("httpx.post", return_value=_mock_completion(payload)):
        result = ai_service.categorize_transaction("SWIGGY ORDER", ["Dining", "Groceries"])
    assert result is None  # "Travel" not in allowed categories


def test_categorize_transaction_returns_none_on_llm_failure():
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = ai_service.categorize_transaction("SWIGGY ORDER", ["Dining"])
    assert result is None


def test_categorize_transaction_returns_none_for_empty_description():
    result = ai_service.categorize_transaction("", ["Dining"])
    assert result is None


def test_categorize_transaction_returns_none_for_empty_categories():
    result = ai_service.categorize_transaction("SWIGGY ORDER", [])
    assert result is None


def test_categorize_transaction_handles_malformed_json():
    with patch("httpx.post", return_value=_mock_completion("not json")):
        result = ai_service.categorize_transaction("SWIGGY ORDER", ["Dining"])
    assert result is None


# ── normalize_merchant ─────────────────────────────────────────────────────────

def test_normalize_merchant_happy_path():
    with patch("httpx.post", return_value=_mock_chat("Swiggy")):
        result = ai_service.normalize_merchant("SWIGGY ORDER 9845")
    assert result == "Swiggy"


def test_normalize_merchant_strips_surrounding_quotes():
    with patch("httpx.post", return_value=_mock_chat('"Amazon"')):
        result = ai_service.normalize_merchant("AMAZON.COM*XY12345")
    assert result == "Amazon"


def test_normalize_merchant_returns_none_on_llm_failure():
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = ai_service.normalize_merchant("AMAZON.COM*XY12345")
    assert result is None


def test_normalize_merchant_returns_none_for_empty_description():
    result = ai_service.normalize_merchant("")
    assert result is None


# ── parse_receipt ─────────────────────────────────────────────────────────────

def test_parse_receipt_happy_path():
    payload = json.dumps({
        "is_receipt": True,
        "merchant": "Starbucks",
        "amount": 12.50,
        "currency": "USD",
        "date": "2026-04-10",
        "category_hint": "Dining",
    })
    with patch("httpx.post", return_value=_mock_chat(payload)):
        result = ai_service.parse_receipt(b"fake-image-bytes", "image/jpeg")
    assert result["is_receipt"] is True
    assert result["merchant"] == "Starbucks"
    assert result["amount"] == 12.50


def test_parse_receipt_returns_false_receipt_dict():
    payload = json.dumps({"is_receipt": False})
    with patch("httpx.post", return_value=_mock_chat(payload)):
        result = ai_service.parse_receipt(b"random-bytes", "image/jpeg")
    assert result == {"is_receipt": False}


def test_parse_receipt_returns_none_on_llm_failure():
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = ai_service.parse_receipt(b"bytes", "image/jpeg")
    assert result is None


def test_parse_receipt_returns_none_on_malformed_json():
    with patch("httpx.post", return_value=_mock_chat("bad json")):
        result = ai_service.parse_receipt(b"bytes", "image/jpeg")
    assert result is None


# ── parse_voice ────────────────────────────────────────────────────────────────

def test_parse_voice_happy_path():
    # parse_voice() is kept for API compatibility but returns None (no audio LLM support).
    # Test parse_voice_transcript() instead — the actual implementation for voice entry.
    payload = json.dumps({
        "is_transaction": True,
        "amount": 45.0,
        "currency": "GBP",
        "description": "Tesco",
        "category_hint": "Groceries",
    })
    with patch("httpx.post", return_value=_mock_chat(payload)):
        result = ai_service.parse_voice_transcript("I spent 45 pounds at Tesco")
    assert result["is_transaction"] is True
    assert result["amount"] == 45.0


def test_parse_voice_non_transaction():
    # parse_voice() is kept for API compatibility but returns None (no audio LLM support).
    # Test parse_voice_transcript() instead.
    payload = json.dumps({"is_transaction": False})
    with patch("httpx.post", return_value=_mock_chat(payload)):
        result = ai_service.parse_voice_transcript("hello how are you")
    assert result == {"is_transaction": False}


def test_parse_voice_returns_none_on_llm_failure():
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = ai_service.parse_voice(b"audio", "audio/webm")
    assert result is None


# ── parse_statement ────────────────────────────────────────────────────────────

def test_parse_statement_image_happy_path():
    rows = json.dumps([
        {"date": "2026-04-01", "description": "Tesco", "amount": 45.0},
        {"date": "2026-04-02", "description": "Costa Coffee", "amount": 4.5},
    ])
    with patch("httpx.post", return_value=_mock_chat(rows)):
        result = ai_service.parse_statement(b"img-bytes", "image/jpeg", "BANK")
    assert result is not None
    assert len(result) == 2
    assert result[0]["description"] == "Tesco"


def test_parse_statement_returns_none_on_llm_failure():
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = ai_service.parse_statement(b"img-bytes", "image/jpeg", "BANK")
    assert result is None


def test_parse_statement_filters_rows_missing_amount():
    rows = json.dumps([
        {"date": "2026-04-01", "description": "Tesco", "amount": 45.0},
        {"date": "2026-04-02", "description": "No amount row"},  # missing amount
    ])
    with patch("httpx.post", return_value=_mock_chat(rows)):
        result = ai_service.parse_statement(b"img-bytes", "image/jpeg", "BANK")
    assert result is not None
    assert len(result) == 1


def test_parse_statement_returns_none_for_empty_list():
    with patch("httpx.post", return_value=_mock_chat("[]")):
        result = ai_service.parse_statement(b"img-bytes", "image/jpeg", "BANK")
    assert result is None  # empty valid list → None (no transactions extracted)


# ── generate_monthly_narrative ─────────────────────────────────────────────────

def test_generate_monthly_narrative_happy_path():
    expected = "The Smith family had a great April with strong savings."
    with patch("httpx.post", return_value=_mock_chat(expected)):
        result = ai_service.generate_monthly_narrative({
            "month": "April 2026",
            "family_name": "Smith",
            "base_currency": "USD",
            "total_income": 8000.0,
            "total_expenses": 5500.0,
            "net_savings": 2500.0,
            "savings_rate": 31.25,
            "top_categories": [{"name": "Groceries", "amount": 800}],
        })
    assert result == expected


def test_generate_monthly_narrative_returns_none_on_llm_failure():
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = ai_service.generate_monthly_narrative({"month": "April 2026"})
    assert result is None


# ── generate_weekly_digest ─────────────────────────────────────────────────────

def test_generate_weekly_digest_happy_path():
    expected = "Spent $400 this week, mostly on groceries."
    with patch("httpx.post", return_value=_mock_chat(expected)):
        result = ai_service.generate_weekly_digest({
            "week_ending": "Apr 12",
            "family_name": "Smith",
            "base_currency": "USD",
            "total_spent": 400.0,
            "top_categories": [{"name": "Groceries", "amount": 200}],
        })
    assert result == expected


def test_generate_weekly_digest_returns_none_on_llm_failure():
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = ai_service.generate_weekly_digest({"week_ending": "Apr 12"})
    assert result is None


# ── _extract_json ─────────────────────────────────────────────────────────────

def test_extract_json_extracts_embedded_json():
    raw = 'Some text before {"key": "value"} and after'
    result = ai_service._extract_json(raw)
    assert result == {"key": "value"}


def test_extract_json_returns_none_for_no_json():
    result = ai_service._extract_json("no json here")
    assert result is None


def test_extract_json_returns_none_for_empty_string():
    result = ai_service._extract_json("")
    assert result is None


def test_extract_json_returns_none_for_malformed_json():
    result = ai_service._extract_json("{bad: json}")
    assert result is None
