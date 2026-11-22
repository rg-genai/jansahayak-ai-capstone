"""Centralized Pydantic settings for JanSahayak AI.

Loads all configuration from `.env` without exposing secrets in logs or reprs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Track B Hosted Inference API (Qwen/Qwen3-8B)
    llm_base_url: str = Field(default="https://103.42.50.41:1031/v1")
    llm_model: str = Field(default="Qwen/Qwen3-8B")
    llm_api_key: SecretStr = Field(default=SecretStr(""))
    llm_ca_cert_path: str = Field(default="certs/vm07-ca.crt")
    llm_max_concurrent_requests: int = Field(default=1, ge=1, le=4)
    llm_max_rpm: int = Field(default=55, ge=1, le=60)
    llm_max_output_tokens: int = Field(default=1024, ge=64, le=1024)

    # Track B Hosted Embeddings API (bge-small-en-v1.5)
    embedding_base_url: str = Field(default="https://103.42.50.41:1035/v1")
    embedding_model: str = Field(default="bge-small-en-v1.5")
    embedding_api_key: SecretStr = Field(default=SecretStr(""))
    embedding_ca_cert_path: str = Field(
        default="Capstone_Overview_resources/API/VM02_Embeddings_Access/vm02-ca.crt"
    )
    embedding_batch_size: int = Field(default=16, ge=1, le=16)

    # Corpus & Retrieval
    ingest_scope: Literal["central", "all"] = Field(default="central")
    reranker_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    web_fallback_threshold: float = Field(default=0.25)
    semantic_cache_threshold: float = Field(default=0.96)
    rate_limit_rpm_per_session: int = Field(default=15, ge=1, le=120)

    # Grievance Execution Mode
    grievance_mode: Literal["sandbox", "assisted", "apisetu"] = Field(default="sandbox")
    mock_cpgrams_base_url: str = Field(default="http://127.0.0.1:8000/mock-cpgrams/v1")

    # Server & Storage
    backend_host: str = Field(default="127.0.0.1")
    backend_port: int = Field(default=8000)
    frontend_origin: str = Field(default="http://localhost:5173")
    database_path: str = Field(default="data/jansahayak.db")
    index_dir: str = Field(default="data/index")

    # Optional Integrations
    tavily_api_key: SecretStr = Field(default=SecretStr(""))
    bhashini_user_id: str = Field(default="")
    bhashini_ulca_api_key: SecretStr = Field(default=SecretStr(""))
    sarvam_api_key: SecretStr = Field(default=SecretStr(""))
    apisetu_client_id: str = Field(default="")
    apisetu_api_key: SecretStr = Field(default=SecretStr(""))

    # Optional SMTP Email for Real CPGRAMS Sandbox Confirmation Emails
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: SecretStr = Field(default=SecretStr(""))
    smtp_from_email: str = Field(default="noreply-sandbox@jansahayak.local")
    smtp_use_tls: bool = Field(default=True)

    def resolve_path(self, relative_or_abs: str) -> Path:
        p = Path(relative_or_abs)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def llm_ca_cert_abs(self) -> Path:
        return self.resolve_path(self.llm_ca_cert_path)

    @property
    def embedding_ca_cert_abs(self) -> Path:
        return self.resolve_path(self.embedding_ca_cert_path)

    @property
    def db_abs_path(self) -> Path:
        return self.resolve_path(self.database_path)

    @property
    def index_abs_dir(self) -> Path:
        return self.resolve_path(self.index_dir)

    @property
    def archive_dir(self) -> Path:
        return PROJECT_ROOT / "archive"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
