"""Google Gemini backend — converts OpenAI-format messages to google-generativeai SDK format."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GoogleAIBackend:
    def __init__(self, settings):
        self.api_key = settings.google_ai_api_key
        self.model = settings.google_ai_model
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
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)

            parts = self._build_parts(messages)
            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.1,
            )
            resp = model.generate_content(parts, generation_config=generation_config)
            return resp.text.strip()
        except Exception as exc:
            logger.warning("Google AI chat failed: %s", exc)
            return None

    def _build_parts(self, messages: list[dict]) -> list:
        import base64
        parts = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        parts.append(part["text"])
                    elif part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        if url.startswith("data:"):
                            header, data = url.split(",", 1)
                            media_type = header.split(";")[0].split(":")[1]
                            try:
                                from google.generativeai.types import Part, Blob
                                parts.append(Part(inline_data=Blob(
                                    mime_type=media_type,
                                    data=base64.b64decode(data),
                                )))
                            except ImportError:
                                # Fallback if Blob/Part not available in this SDK version
                                parts.append({"mime_type": media_type, "data": base64.b64decode(data)})
        return parts

    def is_available(self) -> bool:
        return bool(self.api_key)
