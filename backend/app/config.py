"""Configurazione applicativa: tutto arriva da variabili d'ambiente o da un .env locale."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Generale -----------------------------------------------------------
    app_name: str = "Interview Prep Copilot"
    environment: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"

    # Elenco di origin ammessi dal CORS. In locale Vite gira su 5173.
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Codice di accesso condiviso: l'app e' pensata per un singolo utente.
    # Se vuoto, l'API resta aperta (accettabile solo in locale).
    access_code: str = ""

    # --- Persistenza --------------------------------------------------------
    storage_backend: Literal["json", "azure_tables"] = "json"
    data_dir: str = ".data"
    azure_storage_account_name: str = ""
    azure_storage_connection_string: str = ""
    azure_table_prefix: str = "ipc"
    azure_blob_container: str = "cv-uploads"

    # --- AI (Azure AI Foundry / Azure OpenAI) -------------------------------
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-10-21"
    ai_request_timeout_seconds: float = 90.0
    ai_max_output_tokens: int = 4096

    # I modelli reasoning (o3, o4-mini, gpt-5) contano i token di ragionamento
    # dentro il budget di output: con 4096 il ragionamento si mangia la risposta
    # e torna una stringa vuota. Per loro si usa questo tetto, più alto.
    ai_reasoning_max_output_tokens: int = 16000
    # low | medium | high. Vuoto = non inviarlo, lascia il default del modello.
    ai_reasoning_effort: str = ""
    # auto | standard | reasoning. Con auto la famiglia si deduce dal nome del
    # deployment e si corregge da sola al primo errore dell'API.
    ai_model_family: Literal["auto", "standard", "reasoning"] = "auto"

    # --- Upload CV ----------------------------------------------------------
    max_upload_bytes: int = 5 * 1024 * 1024
    store_cv_files: bool = False

    # --- Esecuzione codice utente -------------------------------------------
    # Spento di default: eseguire codice arbitrario sul server e' un rischio.
    # Vedi docs/security.md prima di accenderlo.
    enable_code_execution: bool = False
    code_execution_timeout_seconds: float = 5.0
    code_execution_memory_mb: int = 256

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        # Permette sia la lista JSON sia la forma "a,b,c" comoda nelle app settings di Azure.
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return value
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @property
    def ai_configured(self) -> bool:
        """L'AI e' utilizzabile solo se conosciamo endpoint e deployment."""
        return bool(self.azure_openai_endpoint and self.azure_openai_deployment)

    @property
    def uses_managed_identity(self) -> bool:
        """Senza API key si passa dalla managed identity (nessun segreto da gestire)."""
        return self.ai_configured and not self.azure_openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
