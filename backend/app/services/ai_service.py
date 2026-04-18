"""
AI Service — public API for all AI features.

All methods return None / False on failure so callers can degrade gracefully.
Backend selection order: family DB preference → LLM_PROVIDER env var → "local" (Ollama).
"""

import json
import logging
import base64
import io
from typing import Optional

logger = logging.getLogger(__name__)


def _get_backend(family_id=None, db=None):
    from app.services.llm_backends.factory import get_backend
    return get_backend(family_id, db)


def _extract_json(text: str) -> Optional[dict]:
    """Extract the first JSON object from a string, stripping markdown code fences."""
    if not text:
        return None
    import re
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None

def is_available(family_id=None, db=None) -> bool:
    """Return True if the configured LLM backend is reachable."""
    return _get_backend(family_id, db).is_available()

def categorize_transaction(
    description: str, categories: list[str], family_id=None, db=None
) -> Optional[dict]:
    """
    Suggest a category for a transaction description.

    Returns: {"category": str, "confidence": "high"|"medium"|"low"} or None.
    """
    if not description or not categories:
        return None

    cat_list = ", ".join(categories)
    prompt = f"""You are a transaction categorizer for a family finance app.
Given a transaction description, return ONLY valid JSON with the category.

Family's categories: [{cat_list}]

Examples:
"SWIGGY ORDER 9845" → {{"category": "Dining", "confidence": "high"}}
"HDFC NEFT SALARY" → {{"category": "Salary", "confidence": "high"}}
"AMAZON.COM*ABC123" → {{"category": "Shopping", "confidence": "medium"}}
"RELIANCE JIO" → {{"category": "Subscriptions", "confidence": "high"}}

Transaction: "{description}"
Return ONLY JSON, nothing else."""

    raw = _get_backend(family_id, db).complete(prompt, max_tokens=64)
    result = _extract_json(raw or "")
    if result and "category" in result and result["category"] in categories:
        return result
    return None

def normalize_merchant(description: str, family_id=None, db=None) -> Optional[str]:
    """
    Return a clean merchant name from a raw transaction description string.
    e.g. "AMAZON.COM*XY12345 AMZN.COM/BILL" → "Amazon"
    """
    if not description:
        return None

    prompt = f"""Clean the following raw bank transaction description into a short, human-readable merchant name.
Return ONLY the merchant name as plain text, nothing else.

Examples:
"SWIGGY ORDER 9845" → "Swiggy"
"AMAZON.COM*XY12345" → "Amazon"
"HDFC BANK NEFT CREDIT" → "HDFC Bank"
"UPI/PHONEPE/9845/PAY" → "PhonePe"
"POS DECATHLON DUBAI" → "Decathlon"

Raw description: "{description}"
Merchant name:"""

    raw = _get_backend(family_id, db).complete(prompt, max_tokens=32)
    if raw:
        return raw.strip().strip('"').strip("'")
    return None

def parse_receipt(
    image_bytes: bytes, mime_type: str = "image/jpeg", family_id=None, db=None
) -> Optional[dict]:
    """
    Parse a receipt image and extract transaction details.

    Returns dict matching ReceiptParseResponse schema or None on failure.
    """
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{mime_type};base64,{b64}"

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
                {
                    "type": "text",
                    "text": (
                        "You are a receipt parser. Extract transaction details from this receipt image.\n"
                        "Return ONLY valid JSON. If the image is not a receipt or bill, return "
                        '{"is_receipt": false}.\n\n'
                        "Schema:\n"
                        "{\n"
                        '  "is_receipt": boolean,\n'
                        '  "merchant": string | null,\n'
                        '  "amount": number | null,\n'
                        '  "currency": "ISO 4217 code" | null,\n'
                        '  "date": "YYYY-MM-DD" | null,\n'
                        '  "category_hint": string | null\n'
                        "}"
                    ),
                },
            ],
        }
    ]

    raw = _get_backend(family_id, db).chat(messages, max_tokens=256)
    result = _extract_json(raw or "")
    if result and result.get("is_receipt"):
        return result
    if result and result.get("is_receipt") is False:
        return {"is_receipt": False}
    return None

def parse_voice(audio_bytes: bytes, mime_type: str = "audio/webm") -> Optional[dict]:
    """
    Kept for API compatibility; audio-only LLMs are not supported by Gemma.
    Use parse_voice_transcript() with a pre-transcribed string instead.
    """
    return None


def parse_voice_transcript(
    transcript: str, family_id=None, db=None
) -> Optional[dict]:
    """
    Extract a transaction draft from a plain-text voice transcript.

    Returns dict matching VoiceParseResponse schema or None on failure.
    """
    if not transcript or not transcript.strip():
        return None

    prompt = f"""You are a financial assistant. A user spoke the following sentence to log a transaction.
Extract the transaction details and return ONLY valid JSON.

Schema:
{{
  "is_transaction": boolean,
  "amount": number | null,
  "currency": "ISO 4217 code" | null,
  "description": string | null,
  "category_hint": string | null
}}

Examples:
"I spent 45 pounds at Tesco" → {{"is_transaction": true, "amount": 45, "currency": "GBP", "description": "Tesco", "category_hint": "Groceries"}}
"paid 200 rupees for petrol" → {{"is_transaction": true, "amount": 200, "currency": "INR", "description": "Petrol", "category_hint": "Transport"}}
"hello how are you" → {{"is_transaction": false, "amount": null, "currency": null, "description": null, "category_hint": null}}

User said: "{transcript.strip()}"
Return ONLY JSON, nothing else."""

    raw = _get_backend(family_id, db).complete(prompt, max_tokens=128)
    result = _extract_json(raw or "")
    if result and result.get("is_transaction"):
        return result
    if result and result.get("is_transaction") is False:
        return {"is_transaction": False}
    return None

def generate_monthly_narrative(
    summary: dict, family_id=None, db=None
) -> Optional[str]:
    """
    Generate a 3–4 sentence plain-English narrative of a family's monthly finances.

    summary keys: month, family_name, base_currency, total_income, total_expenses,
                  net_savings, savings_rate, top_categories, vs_previous_month, vs_budget
    """
    prompt = f"""You are a personal finance advisor writing a brief monthly summary for a family.
Write a warm, 3-4 sentence narrative based on the data below. Use the family name.
Be specific — mention actual numbers and categories. Do not use bullet points.

Data:
{json.dumps(summary, indent=2)}

Monthly summary:"""

    raw = _get_backend(family_id, db).complete(prompt, max_tokens=256)
    return raw if raw else None

def _extract_text_from_pdf(pdf_bytes: bytes, backend) -> Optional[str]:
    """
    Extract text from a PDF using pdfplumber (text-based PDFs).
    Falls back to pymupdf page-image rendering for scanned PDFs.
    Returns extracted text or None.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row:
                                pages_text.append("\t".join(cell or "" for cell in row))
                else:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
            combined = "\n".join(pages_text).strip()
            if len(combined) > 100:
                return combined
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s", exc)

    # Fallback: render pages to images for vision model
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_text = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode()
            data_url = f"data:image/png;base64,{b64}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": "Extract all text from this bank statement page. Output only the raw text content, preserving numbers and dates exactly as shown."},
                    ],
                }
            ]
            raw = backend.chat(messages, max_tokens=1024)
            if raw:
                pages_text.append(raw)
        doc.close()
        return "\n".join(pages_text).strip() or None
    except Exception as exc:
        logger.warning("pymupdf image fallback failed: %s", exc)
        return None


def _extract_transactions_from_text(
    text: str, account_type: str, backend
) -> Optional[list]:
    """
    Ask the LLM to identify expense/debit transactions from extracted statement text.
    account_type: "BANK" or "CREDIT_CARD"
    Returns list of dicts or None.
    """
    if not text:
        return None

    truncated = text[:4000]
    debit_label = "debit/withdrawal" if account_type == "BANK" else "charge/purchase"

    prompt = f"""You are a bank statement parser for a family finance app.
Extract all {debit_label} (expense) transactions from the statement text below.
Ignore credits, deposits, payments, and opening/closing balance rows.

Return ONLY valid JSON array. Each item must have:
  "date": "YYYY-MM-DD",
  "description": "merchant or narration text",
  "amount": positive number (debit amount only)

If no expense transactions found, return [].

Statement text:
\"\"\"
{truncated}
\"\"\"

JSON array:"""

    raw = backend.complete(prompt, max_tokens=1024)
    if not raw:
        return None

    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return None
    try:
        rows = json.loads(raw[start:end])
        valid = [
            r for r in rows
            if isinstance(r, dict) and "amount" in r and "date" in r
        ]
        return valid if valid else None
    except json.JSONDecodeError:
        return None


def parse_statement(
    file_bytes: bytes, mime_type: str, account_type: str = "BANK",
    family_id=None, db=None,
) -> Optional[list]:
    """
    Parse a bank/credit-card statement (PDF or image) and return expense transactions.

    Returns list of {"date", "description", "amount"} dicts or None on failure.
    """
    backend = _get_backend(family_id, db)

    if mime_type == "application/pdf":
        text = _extract_text_from_pdf(file_bytes, backend)
        if not text:
            return None
        return _extract_transactions_from_text(text, account_type, backend)

    # Image statement — pass directly to vision model
    b64 = base64.b64encode(file_bytes).decode()
    data_url = f"data:{mime_type};base64,{b64}"
    debit_label = "debit/withdrawal" if account_type == "BANK" else "charge/purchase"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {
                    "type": "text",
                    "text": (
                        f"You are a bank statement parser. Extract all {debit_label} (expense) transactions from this statement image.\n"
                        "Ignore credits, deposits, and balance rows.\n"
                        "Return ONLY a valid JSON array. Each item: "
                        '{"date": "YYYY-MM-DD", "description": "merchant or narration", "amount": positive number}.\n'
                        "If none found, return []."
                    ),
                },
            ],
        }
    ]

    raw = backend.chat(messages, max_tokens=1024)
    if not raw:
        return None

    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return None
    try:
        rows = json.loads(raw[start:end])
        valid = [r for r in rows if isinstance(r, dict) and "amount" in r and "date" in r]
        return valid if valid else None
    except json.JSONDecodeError:
        return None

def generate_weekly_digest(summary: dict, family_id=None, db=None) -> Optional[str]:
    """
    Generate a 2-sentence weekly spending digest.

    summary keys: week_ending, family_name, base_currency, total_spent,
                  vs_weekly_pace, top_categories
    """
    prompt = f"""You are a personal finance advisor writing a brief weekly spending summary for a family.
Write exactly 2 sentences. Be specific — mention actual numbers and categories.

Data:
{json.dumps(summary, indent=2)}

Weekly digest:"""

    raw = _get_backend(family_id, db).complete(prompt, max_tokens=128)
    return raw if raw else None
