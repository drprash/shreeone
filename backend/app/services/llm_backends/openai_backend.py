"""OpenAI backend — also works for Azure OpenAI, Groq, Together.ai via OPENAI_BASE_URL."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OpenAIBackend:
    def __init__(self, settings):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.base_url = settings.openai_base_url
        self.timeout = settings.llm_timeout_seconds
        self.n_predict = settings.llm_n_predict

    def complete(self, prompt: str, max_tokens: int = None) -> Optional[str]:
        if max_tokens is None:
            max_tokens = self.n_predict
        return self.chat([{"role": "user", "content": prompt}], max_tokens=max_tokens)

    def chat(self, messages: list[dict], max_tokens: int = None) -> Optional[str]:
        if max_tokens is None:
            max_tokens = self.n_predict
        try:
            from openai import OpenAI
            kwargs = {"api_key": self.api_key, "timeout": self.timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            client = OpenAI(**kwargs)
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.1,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("OpenAI chat failed: %s", exc)
            return None

    def is_available(self) -> bool:
        return bool(self.api_key)
