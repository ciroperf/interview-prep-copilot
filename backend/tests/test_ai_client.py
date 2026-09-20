"""Il client deve adattarsi ai parametri che il deployment accetta.

I modelli cambiano API fra una generazione e l'altra: quelli reasoning
rifiutano `temperature` e vogliono `max_completion_tokens`. Qui si verifica che
il client se ne accorga dall'errore e si corregga, senza che nessuno debba
aggiornare una tabella di modelli.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.client import (
    REASONING_STYLE,
    STANDARD_STYLE,
    AIClient,
    adapt_style,
    build_messages,
    guess_style,
)
from app.config import Settings

# Messaggi d'errore nella forma in cui li restituisce davvero Azure OpenAI.
ERRORE_MAX_TOKENS = (
    "Unsupported parameter: 'max_tokens' is not supported with this model. "
    "Use 'max_completion_tokens' instead."
)
ERRORE_TEMPERATURE = (
    "Unsupported value: 'temperature' does not support 0.2 with this model. "
    "Only the default (1) value is supported."
)
ERRORE_RUOLO_SYSTEM = (
    "Unsupported value: 'messages[0].role' does not support 'system'. Use 'developer'."
)
ERRORE_REASONING = "Unrecognized request argument supplied: reasoning_effort"


class FakeCompletions:
    """Finto endpoint: rifiuta i parametri elencati, come farebbe il servizio."""

    def __init__(self, rifiuta: set[str], content: str = '{"esito": "ok"}') -> None:
        self.rifiuta = rifiuta
        self.content = content
        self.chiamate: list[dict] = []

    async def create(self, **kwargs):
        self.chiamate.append(kwargs)
        if "max_tokens" in self.rifiuta and "max_tokens" in kwargs:
            raise RuntimeError(ERRORE_MAX_TOKENS)
        if "temperature" in self.rifiuta and "temperature" in kwargs:
            raise RuntimeError(ERRORE_TEMPERATURE)
        if "reasoning_effort" in self.rifiuta and "reasoning_effort" in kwargs:
            raise RuntimeError(ERRORE_REASONING)
        if "system" in self.rifiuta and kwargs["messages"][0]["role"] == "system":
            raise RuntimeError(ERRORE_RUOLO_SYSTEM)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def build_client(deployment: str, rifiuta: set[str], **extra) -> tuple[AIClient, FakeCompletions]:
    settings = Settings(
        azure_openai_endpoint="https://esempio.openai.azure.com/",
        azure_openai_api_key="finta",
        azure_openai_deployment=deployment,
        **extra,
    )
    client = AIClient(settings)
    fake = FakeCompletions(rifiuta)
    # Iniettiamo il finto client: _ensure_client restituisce quello già presente.
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return client, fake


# --- ipotesi iniziale -------------------------------------------------------


@pytest.mark.parametrize(
    "deployment, reasoning",
    [
        ("gpt-4o-mini", False),
        ("gpt-4o", False),
        ("gpt-4.1", False),
        ("gpt-4.1-mini", False),
        ("o3", True),
        ("o3-mini", True),
        ("o4-mini", True),
        ("gpt-5", True),
        ("gpt-5-mini", True),
        ("gpt-5.4-mini", True),
        ("gpt-5-codex", True),
        # Le varianti "-chat" sono le controparti conversazionali: non ragionano
        # e accettano temperature, quindi vanno trattate come standard.
        ("gpt-5-chat", False),
        ("gpt-5.2-chat", False),
        ("gpt-chat-latest", False),
    ],
)
def test_ipotesi_dal_nome_del_deployment(deployment, reasoning):
    assert guess_style(deployment).is_reasoning is reasoning


def test_la_famiglia_si_puo_forzare():
    assert guess_style("nome-personalizzato", family="reasoning").is_reasoning is True
    assert guess_style("o4-mini", family="standard").is_reasoning is False


# --- adattamento dall'errore ------------------------------------------------


def test_adatta_il_parametro_dei_token():
    adattato = adapt_style(STANDARD_STYLE, ERRORE_MAX_TOKENS)
    assert adattato is not None
    assert adattato.token_param == "max_completion_tokens"


def test_adatta_la_temperatura():
    adattato = adapt_style(STANDARD_STYLE, ERRORE_TEMPERATURE)
    assert adattato is not None
    assert adattato.supports_temperature is False


def test_adatta_il_ruolo_di_sistema():
    adattato = adapt_style(STANDARD_STYLE, ERRORE_RUOLO_SYSTEM)
    assert adattato is not None
    assert adattato.system_role == "developer"


def test_adatta_il_reasoning_effort():
    adattato = adapt_style(REASONING_STYLE, ERRORE_REASONING)
    assert adattato is not None
    assert adattato.send_reasoning_effort is False


def test_un_errore_non_negoziabile_non_produce_adattamenti():
    assert adapt_style(STANDARD_STYLE, "429 Too Many Requests: quota exceeded") is None
    assert adapt_style(STANDARD_STYLE, "401 Unauthorized") is None


def test_ruolo_merged_unisce_sistema_e_utente():
    from dataclasses import replace

    messaggi = build_messages(replace(STANDARD_STYLE, system_role="merged"), "SIS", "UTE")
    assert len(messaggi) == 1
    assert messaggi[0]["role"] == "user"
    assert "SIS" in messaggi[0]["content"] and "UTE" in messaggi[0]["content"]


# --- comportamento end-to-end ----------------------------------------------


async def test_un_modello_standard_usa_temperature_e_max_tokens():
    client, fake = build_client("gpt-4o-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")

    assert len(fake.chiamate) == 1, "nessun tentativo sprecato"
    chiamata = fake.chiamate[0]
    assert "max_tokens" in chiamata
    assert chiamata["temperature"] == 0.2
    assert chiamata["messages"][0]["role"] == "system"


async def test_un_modello_reasoning_parte_gia_con_i_parametri_giusti():
    """Il nome fa da ipotesi: su o4-mini non si spreca una chiamata per scoprirlo."""
    client, fake = build_client("o4-mini", rifiuta={"max_tokens", "temperature"})
    await client.complete_json("sistema", "utente")

    assert len(fake.chiamate) == 1
    chiamata = fake.chiamate[0]
    assert "max_completion_tokens" in chiamata
    assert "max_tokens" not in chiamata
    assert "temperature" not in chiamata
    assert chiamata["messages"][0]["role"] == "developer"


async def test_un_deployment_dal_nome_ingannevole_viene_corretto_dall_errore():
    """Il caso che conta: un modello nuovo con un nome che l'euristica non conosce."""
    client, fake = build_client("modello-aziendale-v2", rifiuta={"max_tokens", "temperature"})
    await client.complete_json("sistema", "utente")

    # Tre tentativi: max_tokens rifiutato, poi temperature, poi passa.
    assert len(fake.chiamate) == 3
    assert "max_completion_tokens" in fake.chiamate[-1]
    assert "temperature" not in fake.chiamate[-1]
    assert client.style.is_reasoning is True


async def test_lo_stile_appreso_non_viene_ricercato_a_ogni_chiamata():
    client, fake = build_client("modello-aziendale-v2", rifiuta={"max_tokens"})
    await client.complete_json("sistema", "utente")
    tentativi_primo_giro = len(fake.chiamate)

    await client.complete_json("sistema", "utente")
    assert len(fake.chiamate) == tentativi_primo_giro + 1, (
        "il secondo giro deve costare una sola chiamata"
    )


async def test_il_reasoning_effort_viene_inviato_solo_se_configurato():
    client, fake = build_client("o4-mini", rifiuta=set(), ai_reasoning_effort="high")
    await client.complete_json("sistema", "utente")
    assert fake.chiamate[0]["reasoning_effort"] == "high"

    client, fake = build_client("o4-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")
    assert "reasoning_effort" not in fake.chiamate[0]


async def test_i_modelli_reasoning_ricevono_un_budget_di_token_piu_alto():
    """I token di ragionamento contano nel budget: con 4096 la risposta sparisce."""
    client, fake = build_client("o4-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")
    assert fake.chiamate[0]["max_completion_tokens"] == 16000

    client, fake = build_client("gpt-4o-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")
    assert fake.chiamate[0]["max_tokens"] == 4096


async def test_un_errore_non_negoziabile_viene_propagato():
    client, fake = build_client("gpt-4o-mini", rifiuta=set())

    async def sempre_429(**_kwargs):
        raise RuntimeError("429 Too Many Requests")

    fake.create = sempre_429
    with pytest.raises(RuntimeError, match="429"):
        await client.complete_json("sistema", "utente")


async def test_risposta_vuota_da_reasoning_spiega_cosa_cambiare():
    client, fake = build_client("o4-mini", rifiuta=set())
    fake.content = ""
    with pytest.raises(RuntimeError, match="AI_REASONING_MAX_OUTPUT_TOKENS"):
        await client.complete_json("sistema", "utente")



async def test_una_variante_chat_usa_i_parametri_standard():
    """gpt-5-chat sta nella famiglia 5 ma non ragiona: perdere temperature
    sarebbe una regressione silenziosa sulla qualità delle generazioni."""
    client, fake = build_client("gpt-5-chat", rifiuta=set())
    await client.complete_json("sistema", "utente", temperature=0.7)

    assert len(fake.chiamate) == 1
    assert fake.chiamate[0]["temperature"] == 0.7
    assert "max_tokens" in fake.chiamate[0]
