"""Lettura della configurazione dalle variabili d'ambiente.

Il caso che conta davvero è CORS_ORIGINS: il Terraform la passa come elenco
separato da virgole, e pydantic-settings, lasciato a sé, prova a interpretarla
come JSON e fa fallire l'avvio dell'applicazione. Un errore qui non si vede in
sviluppo e si manifesta come container che non parte in Azure.
"""

from __future__ import annotations

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "valore, atteso",
    [
        # La forma che usa il Terraform.
        ("http://a.it,http://b.it", ["http://a.it", "http://b.it"]),
        # Spazi e virgole di troppo non devono dare fastidio.
        (" http://a.it , http://b.it , ", ["http://a.it", "http://b.it"]),
        # La forma JSON resta accettata.
        ('["http://a.it","http://b.it"]', ["http://a.it", "http://b.it"]),
        ("http://solo.it", ["http://solo.it"]),
        ("", []),
    ],
)
def test_cors_origins_dalle_variabili_ambiente(monkeypatch, valore, atteso):
    monkeypatch.setenv("CORS_ORIGINS", valore)
    assert Settings().cors_origins == atteso


def test_cors_origins_ha_un_default_per_lo_sviluppo(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert "http://localhost:5173" in Settings().cors_origins


def test_json_malformato_da_un_errore_comprensibile(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "[non chiuso")
    with pytest.raises(ValueError, match="non è JSON valido"):
        Settings()


def test_auth_mode_dalle_variabili_ambiente(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "entra_id")
    assert Settings().auth_mode == "entra_id"


def test_auth_mode_sconosciuto_viene_rifiutato(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "qualcosa")
    with pytest.raises(ValueError):
        Settings()


def test_i_default_del_modello_sono_quelli_documentati():
    """Se cambiano, devono cambiare anche README e docs/modelli.md."""
    settings = Settings()
    assert settings.azure_openai_deployment == "gpt-5-mini"
    assert settings.ai_reasoning_effort == "high"
    assert settings.ai_reasoning_max_output_tokens > settings.ai_max_output_tokens


def test_il_budget_regge_un_effort_alto():
    """Effort e budget sono un parametro solo in due pezzi.

    I token di ragionamento si contano dentro il budget di output: con un
    effort alto e un tetto basso il modello ragiona, esaurisce il budget e
    restituisce una stringa vuota. Alzare l'uno senza l'altro rompe le
    chiamate invece di migliorarle.
    """
    settings = Settings()
    if settings.ai_reasoning_effort in {"medium", "high"}:
        assert settings.ai_reasoning_max_output_tokens >= 24000, (
            "con effort alto servono almeno 24k token, o la risposta torna vuota"
        )


def test_il_timeout_sta_sotto_quello_dell_ingress():
    """Container Apps chiude la richiesta a 240 secondi.

    Un timeout piu' alto non verrebbe mai raggiunto: il client vedrebbe cadere
    la connessione invece di ricevere un errore leggibile.
    """
    assert 30 <= Settings().ai_request_timeout_seconds <= 230


def test_ai_configured_richiede_endpoint_e_deployment(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    assert Settings().ai_configured is False

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    assert Settings().ai_configured is True


def test_senza_chiave_si_usa_la_managed_identity(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    assert Settings().uses_managed_identity is True

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "una-chiave")
    assert Settings().uses_managed_identity is False
