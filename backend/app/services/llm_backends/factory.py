"""
LLM backend factory — resolves the right backend for a given family.

Resolution order:
  1. family_preferences.ai_provider (if family_id + db provided)
  2. settings.llm_provider env var
  3. "local" (Ollama — the default)
"""

from typing import Optional
from sqlalchemy.orm import Session


def get_backend(family_id=None, db: Optional[Session] = None):
    """Return the LLM backend configured for the given family (or server default)."""
    from app.config import settings
    provider = _resolve_provider(family_id, db, settings)
    return _build_backend(provider, settings)


_VALID_PROVIDERS = {"local", "openai", "anthropic", "google"}


def _resolve_provider(family_id, db, settings) -> str:
    # 1. Per-family DB preference
    if family_id is not None and db is not None:
        try:
            from app import models
            prefs = db.query(models.FamilyPreference).filter(
                models.FamilyPreference.family_id == family_id
            ).first()
            provider_val = getattr(prefs, "ai_provider", None) if prefs else None
            if isinstance(provider_val, str) and provider_val in _VALID_PROVIDERS:
                return provider_val
        except Exception:
            pass
    # 2. Server-level env var
    if settings.llm_provider and settings.llm_provider != "local":
        return settings.llm_provider
    # 3. Default: local (Ollama)
    return "local"


def _build_backend(provider: str, settings):
    match provider:
        case "openai":
            from app.services.llm_backends.openai_backend import OpenAIBackend
            return OpenAIBackend(settings)
        case "anthropic":
            from app.services.llm_backends.anthropic_backend import AnthropicBackend
            return AnthropicBackend(settings)
        case "google":
            from app.services.llm_backends.google_backend import GoogleAIBackend
            return GoogleAIBackend(settings)
        case _:
            from app.services.llm_backends.ollama import OllamaBackend
            return OllamaBackend(settings)


def get_effective_provider(family_id=None, db=None) -> str:
    """Return the provider name that will be used for the given family."""
    from app.config import settings
    return _resolve_provider(family_id, db, settings)


def get_configured_providers(settings) -> list[str]:
    """Return list of providers that have API keys configured on this server."""
    providers = ["local"]  # local (Ollama) is always available
    if settings.openai_api_key:
        providers.append("openai")
    if settings.anthropic_api_key:
        providers.append("anthropic")
    if settings.google_ai_api_key:
        providers.append("google")
    return providers
