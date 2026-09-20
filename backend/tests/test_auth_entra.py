"""Modalità di accesso: codice condiviso oppure login Microsoft.

Con entra_id la validazione del token avviene prima dell'applicazione, nel
livello di autenticazione integrata di Container Apps. Qui si verifica che il
backend si fidi dell'identità che quel livello inietta, e che rifiuti quando
non c'è: è la rete di sicurezza contro una configurazione incompleta.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def entra_client(data_dir: str) -> Iterator[TestClient]:
    from app.config import get_settings
    from app.services.knowledge import get_knowledge_base
    from app.storage.factory import get_blob_store, get_repository

    os.environ["DATA_DIR"] = data_dir
    os.environ["AUTH_MODE"] = "entra_id"
    # Volutamente valorizzato: in modalità Entra non deve più contare.
    os.environ["ACCESS_CODE"] = "codice-che-non-serve-piu"
    for cache in (get_settings, get_repository, get_blob_store, get_knowledge_base):
        cache.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as client:
        yield client

    os.environ["AUTH_MODE"] = "access_code"
    os.environ["ACCESS_CODE"] = ""
    for cache in (get_settings, get_repository, get_blob_store, get_knowledge_base):
        cache.cache_clear()


def test_senza_identita_la_richiesta_viene_rifiutata(entra_client):
    response = entra_client.get("/api/knowledge/topics")
    assert response.status_code == 401
    assert "Microsoft" in response.json()["detail"]
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_con_l_identita_iniettata_la_richiesta_passa(entra_client):
    response = entra_client.get(
        "/api/knowledge/topics",
        headers={
            "X-MS-CLIENT-PRINCIPAL-ID": "00000000-1111-2222-3333-444444444444",
            "X-MS-CLIENT-PRINCIPAL-NAME": "ciro@esempio.it",
        },
    )
    assert response.status_code == 200


def test_basta_uno_dei_due_header(entra_client):
    """L'autenticazione integrata non sempre valorizza entrambi."""
    assert (
        entra_client.get(
            "/api/knowledge/topics",
            headers={"X-MS-CLIENT-PRINCIPAL-NAME": "ciro@esempio.it"},
        ).status_code
        == 200
    )


def test_il_codice_di_accesso_non_apre_piu_nulla(entra_client):
    """Passando a Entra, un vecchio codice in giro non deve restare una scorciatoia."""
    response = entra_client.get(
        "/api/knowledge/topics",
        headers={"X-Access-Code": "codice-che-non-serve-piu"},
    )
    assert response.status_code == 401


def test_health_e_meta_restano_pubblici(entra_client):
    """Servono alle probe e al bootstrap del frontend prima del login."""
    assert entra_client.get("/api/health").status_code == 200

    meta = entra_client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["auth_mode"] == "entra_id"
    assert meta.json()["access_code_required"] is False


def test_in_modalita_codice_il_principal_non_basta(client):
    """Il contrario: senza Entra attivo, quegli header non devono valere nulla."""
    import os as _os

    from app.config import get_settings

    _os.environ["ACCESS_CODE"] = "segreto"
    get_settings.cache_clear()
    try:
        response = client.get(
            "/api/knowledge/topics",
            headers={"X-MS-CLIENT-PRINCIPAL-NAME": "chiunque@esempio.it"},
        )
        assert response.status_code == 401
    finally:
        _os.environ["ACCESS_CODE"] = ""
        get_settings.cache_clear()
