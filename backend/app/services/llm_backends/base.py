"""LLM backend Protocol — all backends must implement these three methods."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMBackend(Protocol):
    def complete(self, prompt: str, max_tokens: int) -> Optional[str]: ...
    def chat(self, messages: list[dict], max_tokens: int) -> Optional[str]: ...
    def is_available(self) -> bool: ...
