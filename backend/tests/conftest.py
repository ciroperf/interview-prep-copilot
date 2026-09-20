"""Fixture comuni: ogni test gira su uno storage isolato e senza AI."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

# Le impostazioni si leggono dall'ambiente alla prima import: vanno fissate prima.
os.environ.setdefault("ACCESS_CODE", "")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "")
os.environ.setdefault("STORAGE_BACKEND", "json")


@pytest.fixture
def data_dir() -> Iterator[str]:
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


@pytest.fixture
def settings(data_dir: str):
    from app.config import Settings

    return Settings(data_dir=data_dir, storage_backend="json", access_code="")


@pytest.fixture
def kb():
    """Istanza pulita: i test che ampliano il catalogo non devono influenzarsi."""
    from app.services.knowledge import KnowledgeBase

    return KnowledgeBase()


@pytest.fixture
def offline_ai(settings):
    """Client AI non configurato: forza i servizi sui percorsi deterministici."""
    from app.ai.client import AIClient

    return AIClient(settings)


@pytest.fixture
def client(data_dir: str) -> Iterator:
    """TestClient con storage su cartella temporanea e cache delle dipendenze pulita."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.services.knowledge import get_knowledge_base
    from app.storage.factory import get_blob_store, get_repository

    os.environ["DATA_DIR"] = data_dir
    get_settings.cache_clear()
    get_repository.cache_clear()
    get_blob_store.cache_clear()
    # Il catalogo è un singleton: va ricostruito, altrimenti gli argomenti
    # aggiunti da un test restano visibili ai successivi.
    get_knowledge_base.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_repository.cache_clear()
    get_blob_store.cache_clear()
    get_knowledge_base.cache_clear()


SAMPLE_JOB = """
Senior Backend Engineer - Acme Pay

Cerchiamo un Senior Backend Engineer da inserire nel team Payments a Milano, con
modalità di lavoro ibrida.

Responsabilità:
- Progettare e sviluppare microservizi in Python con FastAPI
- Garantire l'affidabilità dei flussi di pagamento e la loro idempotenza
- Collaborare al design di nuove API REST consumate dai team mobile

Requisiti:
- Almeno 5 anni di esperienza nello sviluppo backend
- Ottima conoscenza di Python e PostgreSQL
- Esperienza con Kafka e architetture a microservizi
- Familiarità con Docker e Kubernetes
- Conoscenza di Redis per il caching

Nice to have:
- Esperienza con Terraform
- Conoscenza di GraphQL
"""
