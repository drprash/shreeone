from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database — either a full URL or individual components (preferred when password has special chars)
    database_url: Optional[str] = None
    db_host: Optional[str] = None
    db_port: int = 5432
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 180
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 300
    refresh_rate_limit_requests: int = 30
    refresh_rate_limit_window_seconds: int = 300
    rate_limit_max_keys: int = 10000
    rate_limit_prune_batch_size: int = 1000
    # App
    app_name: str = "ShreeOne Family Finance"
    debug: bool = False
    # CORS
    frontend_url: str = "http://localhost:5173"
    # LLM / local AI (Ollama)
    llm_base_url: str = "http://llm:11434"
    llm_timeout_seconds: float = 90.0
    llm_n_predict: int = 512
    llm_model: str = "gemma4:e4b"
    # Cloud LLM providers (all optional — set API keys in .env to enable)
    llm_provider: str = "local"           # local | openai | anthropic | google
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: Optional[str] = None  # Azure, Groq, or any OpenAI-compatible endpoint
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-haiku-4-5-20251001"
    google_ai_api_key: Optional[str] = None
    google_ai_model: str = "gemini-2.0-flash"

    class Config:
        env_file = ".env"

settings = Settings()
