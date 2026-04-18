"""Ollama backend — extracted from ai_service.py, zero behaviour change."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class OllamaBackend:
    def __init__(self, settings):
        self.base_url = settings.llm_base_url
        self.timeout = settings.llm_timeout_seconds
        self.n_predict = settings.llm_n_predict
        self.model = settings.llm_model

    def complete(self, prompt: str, max_tokens: int = None) -> Optional[str]:
        if max_tokens is None:
            max_tokens = self.n_predict
        return self.chat([{"role": "user", "content": prompt}], max_tokens=max_tokens)

    def chat(self, messages: list[dict], max_tokens: int = None) -> Optional[str]:
        if max_tokens is None:
            max_tokens = self.n_predict
        try:
            resp = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Ollama /v1/chat/completions failed: %s", exc)
            return None

    def is_available(self) -> bool:
        """Return True if Ollama service is reachable. GET / returns 200 Ollama is running."""
        try:
            resp = httpx.get(f"{self.base_url}/", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False
