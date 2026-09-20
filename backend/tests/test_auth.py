"""Il codice di accesso protegge le rotte applicative ma non l'health check."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def protected_client(data_dir: str) -> Iterator[TestClient]:
    from app.config import get_settings
    from app.storage.factory import get_blob_store, get_repository

    os.environ["DATA_DIR"] = data_dir
    os.environ["ACCESS_CODE"] = "codice-segreto"
    get_settings.cache_clear()
    get_repository.cache_clear()
    get_blob_store.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as client:
        yield client

    os.environ["ACCESS_CODE"] = ""
    get_settings.cache_clear()
    get_repository.cache_clear()
    get_blob_store.cache_clear()


def test_health_resta_pubblico(protected_client):
    assert protected_client.get("/api/health").status_code == 200


def test_senza_codice_401(protected_client):
    assert protected_client.get("/api/knowledge/topics").status_code == 401


def test_codice_errato_401(protected_client):
    response = protected_client.get(
        "/api/knowledge/topics", headers={"X-Access-Code": "sbagliato"}
    )
    assert response.status_code == 401


def test_codice_corretto_passa(protected_client):
    response = protected_client.get(
        "/api/knowledge/topics", headers={"X-Access-Code": "codice-segreto"}
    )
    assert response.status_code == 200
