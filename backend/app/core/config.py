"""Application settings loaded from environment variables and backend/.env.

Real environment variables take priority over values in .env.
Secrets are stored as SecretStr so they are masked if a Settings object is
printed or logged (they show as '**********').
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/ folder, so .env is found no matter which directory you run from.
BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"


def _split_csv(value):
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- general -----------------------------------------------------------
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # --- database ----------------------------------------------------------
    # postgresql+psycopg://interview_coach_user:<password>@localhost:5432/interview_coach
    # Optional so the app (and /health) still starts when it is not set.
    database_url: SecretStr | None = None
    # Separate PostgreSQL database for the migration tests (name must end in _test).
    test_database_url: SecretStr | None = None

    # --- HTTP --------------------------------------------------------------
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    allowed_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1"]

    # --- authentication ----------------------------------------------------
    # Secret used to sign access tokens (HS256). Required in production.
    # Generate one with:  python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_days: int = Field(default=7, ge=1, le=90)
    # None = automatic: Secure cookies in production, plain HTTP allowed locally.
    cookie_secure: bool | None = None
    # scrypt cost (2**n). 17 = 128 MiB per hash, the OWASP minimum. Tests lower it.
    password_hash_cost: int = Field(default=17, ge=10, le=20)
    # Login/register attempts allowed per client IP per minute.
    auth_rate_limit_per_minute: int = Field(default=10, ge=1)

    # --- CV upload ---------------------------------------------------------
    cv_storage_dir: Path = BACKEND_DIR / "storage" / "cvs"
    max_cv_bytes: int = 5 * 1024 * 1024
    cv_min_text_chars: int = 50
    cv_max_pdf_pages: int = 30

    # --- question bank and evaluation -------------------------------------
    question_bank_path: Path = APP_DIR / "data" / "question_bank.json"
    skills_list_path: Path = APP_DIR / "data" / "skills.txt"
    # "lexical": dependency-free term overlap (default, runs anywhere).
    # "sbert": local Sentence-Transformers model (needs requirements-ml.txt).
    similarity_backend: Literal["lexical", "sbert"] = "lexical"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_path: str | None = None

    # --- optional LLM (Milestone 5) -----------------------------------------
    # Off by default (API spec D4: no paid or external AI service in the MVP).
    # "openai_compatible" talks to any server with the OpenAI chat-completions API:
    # a local one (Ollama, LM Studio, llama.cpp) or a hosted one.
    llm_provider: Literal["none", "openai_compatible"] = "none"
    llm_base_url: str | None = None  # e.g. http://localhost:11434/v1 for Ollama
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    # A non-local base URL is refused unless this is true: interview answers would leave the machine.
    llm_allow_external: bool = False
    # Which tasks may use the LLM: "agent" (follow-up decisions), "evaluation" (bounded rubric review).
    llm_features: Annotated[list[str], NoDecode] = ["agent", "evaluation"]
    llm_timeout_seconds: float = Field(default=12.0, gt=0, le=120)
    llm_max_retries: int = Field(default=1, ge=0, le=3)
    # After this many consecutive failures the LLM is skipped for llm_cooldown_seconds.
    llm_failure_threshold: int = Field(default=3, ge=1, le=20)
    llm_cooldown_seconds: int = Field(default=120, ge=5, le=3600)

    @field_validator("cors_origins", "allowed_hosts", "llm_features", mode="before")
    @classmethod
    def _parse_list(cls, value):
        return _split_csv(value)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure


@lru_cache
def get_settings() -> Settings:
    return Settings()
