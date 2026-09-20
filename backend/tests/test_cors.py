"""CORS: è il browser a decidere se la chiamata parte, non il backend.

Il caso che è sfuggito una volta: con il login Microsoft il frontend allega
`Authorization: Bearer ...`, il browser manda prima un preflight e, se
l'header non è fra quelli ammessi, riceve 400 e la richiesta vera non parte
mai. Dal lato applicazione si vede solo silenzio.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

ORIGIN = "https://esempio.azurestaticapps.net"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("CORS_ORIGINS", ORIGIN)
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def preflight(client: TestClient, headers: str) -> object:
    return client.options(
        "/api/meta",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": headers,
        },
    )


def test_il_preflight_ammette_il_token_di_entra(client):
    risposta = preflight(client, "authorization")
    assert risposta.status_code == 200
    ammessi = risposta.headers["access-control-allow-headers"].lower()
    assert "authorization" in ammessi


def test_il_preflight_ammette_anche_il_codice_di_accesso(client):
    risposta = preflight(client, "x-access-code")
    assert risposta.status_code == 200


def test_un_origin_estraneo_non_viene_ammesso(client):
    risposta = client.get("/api/meta", headers={"Origin": "https://altro.example"})
    assert "access-control-allow-origin" not in risposta.headers


def test_la_risposta_porta_l_origin_ammesso(client):
    risposta = client.get("/api/meta", headers={"Origin": ORIGIN})
    assert risposta.headers["access-control-allow-origin"] == ORIGIN


def test_senza_origin_configurati_la_cors_la_fa_qualcun_altro(monkeypatch):
    """In Azure con il login Microsoft risponde l'ingress di Container Apps.

    Due strati che aggiungono le stesse intestazioni ne producono di doppie, e
    il browser rifiuta la risposta: qui l'applicazione deve stare zitta.
    """
    monkeypatch.setenv("CORS_ORIGINS", "")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        risposta = client.get("/api/meta", headers={"Origin": ORIGIN})
        assert risposta.status_code == 200
        assert "access-control-allow-origin" not in risposta.headers
    finally:
        get_settings.cache_clear()
