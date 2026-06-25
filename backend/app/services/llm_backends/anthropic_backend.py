"""Anthropic Claude backend — converts OpenAI-format messages to Anthropic API format."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AnthropicBackend:
    def __init__(self, settings):
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model
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
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)

            # Anthropic separates system messages from the messages array
            system = None
            chat_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    system = msg.get("content", "")
                else:
                    chat_messages.append(self._convert_message(msg))

            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": chat_messages,
            }
            if system:
                kwargs["system"] = system

            resp = client.messages.create(**kwargs)
            return resp.content[0].text.strip()
        except Exception as exc:
            logger.warning("Anthropic chat failed: %s", exc)
            return None

    def _convert_message(self, msg: dict) -> dict:
        """Convert OpenAI-format message content to Anthropic format (handles vision)."""
        content = msg.get("content")
        if isinstance(content, str):
            return {"role": msg["role"], "content": content}

        converted_parts = []
        for part in content:
            if part.get("type") == "text":
                converted_parts.append({"type": "text", "text": part["text"]})
            elif part.get("type") == "image_url":
                url = part["image_url"]["url"]
                if url.startswith("data:"):
                    # data:image/jpeg;base64,<data>
                    header, data = url.split(",", 1)
                    media_type = header.split(";")[0].split(":")[1]
                    converted_parts.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    })
                else:
                    converted_parts.append({
                        "type": "image",
                        "source": {"type": "url", "url": url},
                    })
        return {"role": msg["role"], "content": converted_parts}

    def is_available(self) -> bool:
        return bool(self.api_key)
