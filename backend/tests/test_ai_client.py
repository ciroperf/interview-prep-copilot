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
    is_api_version_error,
    supported_api_versions,
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
        self.versioni_viste: list[str] = []
        # Se valorizzato, accetta solo queste api-version e rifiuta le altre
        # elencando quelle supportate, come fa il servizio vero.
        self.versioni_valide: set[str] | None = None
        self.client = None

    async def create(self, **kwargs):
        if self.client is not None:
            self.versioni_viste.append(self.client.api_version)
        if self.versioni_valide is not None and self.client is not None:
            corrente = self.client.api_version
            if corrente not in self.versioni_valide:
                elenco = ", ".join(sorted(self.versioni_valide))
                raise RuntimeError(
                    f"Invalid API version '{corrente}'. Supported versions: {elenco}."
                )
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
    fake.client = client
    finto = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    # Agganciamo il finto a _ensure_client e non a _client: quando il client
    # cambia api-version azzera _client per ricostruirlo, e con la sola
    # iniezione su _client proverebbe a costruirne uno vero.
    client._ensure_client = lambda: finto  # type: ignore[method-assign]
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

    # Vuoto significa "lascia decidere al modello": il parametro non va inviato.
    client, fake = build_client("o4-mini", rifiuta=set(), ai_reasoning_effort="")
    await client.complete_json("sistema", "utente")
    assert "reasoning_effort" not in fake.chiamate[0]


async def test_il_default_manda_reasoning_effort_high():
    """Il default punta a gpt-5-mini con effort alto.

    E' una scelta esplicita per un'app a utente singolo, dove la precisione
    vale piu' della latenza e del costo. Su un deployment pubblico andrebbe
    abbassata da AI_REASONING_EFFORT, non nel codice.
    """
    client, fake = build_client("gpt-5-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")
    assert fake.chiamate[0]["reasoning_effort"] == "high"


async def test_un_modello_standard_non_riceve_reasoning_effort():
    """Il default e' 'low', ma su un modello che non ragiona sarebbe rifiutato."""
    client, fake = build_client("gpt-4.1-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")
    assert "reasoning_effort" not in fake.chiamate[0]


async def test_i_modelli_reasoning_ricevono_un_budget_di_token_piu_alto():
    """I token di ragionamento contano nel budget: con 4096 la risposta sparisce."""
    from app.config import Settings

    attese = Settings()
    client, fake = build_client("o4-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")
    assert fake.chiamate[0]["max_completion_tokens"] == attese.ai_reasoning_max_output_tokens

    client, fake = build_client("gpt-4o-mini", rifiuta=set())
    await client.complete_json("sistema", "utente")
    assert fake.chiamate[0]["max_tokens"] == attese.ai_max_output_tokens


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



# --- fallback sulla api-version ---------------------------------------------


def test_riconosce_un_errore_di_api_version():
    assert is_api_version_error("Invalid API version '2025-01-01-preview'.") is True
    assert is_api_version_error("429 Too Many Requests") is False


def test_estrae_le_versioni_supportate_dalla_piu_recente():
    errore = (
        "Invalid API version '2030-01-01-preview'. Supported versions: "
        "2024-10-21, 2025-04-01-preview, 2024-12-01-preview."
    )
    assert supported_api_versions(errore) == [
        "2030-01-01-preview",
        "2025-04-01-preview",
        "2024-12-01-preview",
        "2024-10-21",
    ]


def test_a_parita_di_data_la_ga_viene_prima_della_preview():
    versioni = supported_api_versions("Supported: 2025-01-01-preview, 2025-01-01.")
    assert versioni == ["2025-01-01", "2025-01-01-preview"]


async def test_una_api_version_inesistente_viene_sostituita_da_sola():
    """Il caso che conta: la versione nel Terraform non esiste piu'. Senza questo
    l'AI smetterebbe di funzionare in silenzio, ricadendo sulle euristiche."""
    client, fake = build_client(
        "gpt-5-mini", rifiuta=set(), azure_openai_api_version="2030-01-01-preview"
    )
    fake.versioni_valide = {"2024-10-21", "2025-04-01-preview"}

    await client.complete_json("sistema", "utente")

    assert client.api_version == "2025-04-01-preview", "deve scegliere la più recente offerta"
    assert fake.versioni_viste[0] == "2030-01-01-preview", (
        "il primo tentativo deve usare la versione configurata"
    )


async def test_la_versione_corretta_viene_ricordata():
    client, fake = build_client(
        "gpt-5-mini", rifiuta=set(), azure_openai_api_version="2030-01-01-preview"
    )
    fake.versioni_valide = {"2025-04-01-preview"}

    await client.complete_json("sistema", "utente")
    chiamate_primo_giro = len(fake.versioni_viste)

    await client.complete_json("sistema", "utente")
    assert len(fake.versioni_viste) == chiamate_primo_giro + 1, (
        "il secondo giro non deve ripetere la ricerca della versione"
    )


async def test_se_nessuna_versione_e_utilizzabile_l_errore_arriva_all_utente():
    client, fake = build_client(
        "gpt-5-mini", rifiuta=set(), azure_openai_api_version="2030-01-01-preview"
    )
    # Il servizio rifiuta e non propone alternative: non c'è niente da provare.
    fake.versioni_valide = set()

    with pytest.raises(RuntimeError, match="Invalid API version"):
        await client.complete_json("sistema", "utente")


async def test_version_e_stile_si_correggono_nella_stessa_sequenza():
    """Versione sbagliata e parametri sbagliati insieme: devono risolversi entrambi."""
    client, fake = build_client(
        "deployment-anonimo",
        rifiuta={"max_tokens", "temperature"},
        azure_openai_api_version="2030-01-01-preview",
    )
    fake.versioni_valide = {"2025-04-01-preview"}

    await client.complete_json("sistema", "utente")

    assert client.api_version == "2025-04-01-preview"
    assert client.style.is_reasoning is True
    assert "max_completion_tokens" in fake.chiamate[-1]
