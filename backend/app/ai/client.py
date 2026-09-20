"""Client verso i modelli deployati su Azure AI Foundry (endpoint Azure OpenAI).

Due modalita' di autenticazione:
  * API key  -> comoda in locale, la chiave sta nel .env;
  * managed identity -> usata in Azure, nessun segreto nell'app.

L'app resta utilizzabile anche senza AI: i servizi ricadono su euristiche
deterministiche quando `available` e' False (vedi services/*.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, replace
from typing import Any

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

# Prefissi dei deployment che appartengono alla famiglia "reasoning". Sono solo
# un'ipotesi iniziale per evitare una chiamata sprecata: se è sbagliata, la
# correzione avviene al primo errore dell'API (vedi adapt_style).
REASONING_PREFIXES = ("o1", "o3", "o4", "o5", "gpt-5")


@dataclass(frozen=True)
class CallStyle:
    """Come parlare con un deployment.

    I modelli cambiano i parametri accettati da una generazione all'altra:
    quelli reasoning vogliono `max_completion_tokens` invece di `max_tokens`,
    rifiutano `temperature` e preferiscono il ruolo `developer` a `system`.
    Invece di inseguire il catalogo con una tabella da aggiornare a ogni
    release, partiamo da un'ipotesi e la correggiamo leggendo l'errore dell'API.
    """

    token_param: str = "max_tokens"
    supports_temperature: bool = True
    system_role: str = "system"  # system | developer | merged
    send_reasoning_effort: bool = False

    @property
    def is_reasoning(self) -> bool:
        return self.token_param == "max_completion_tokens"


STANDARD_STYLE = CallStyle()
REASONING_STYLE = CallStyle(
    token_param="max_completion_tokens",
    supports_temperature=False,
    system_role="developer",
    send_reasoning_effort=True,
)


def guess_style(deployment: str, family: str = "auto") -> CallStyle:
    """Ipotesi iniziale sullo stile, dedotta dal nome del deployment."""
    if family == "reasoning":
        return REASONING_STYLE
    if family == "standard":
        return STANDARD_STYLE
    name = deployment.lower().strip()
    # Le varianti "-chat" (gpt-5-chat, gpt-5.2-chat, gpt-chat-latest) sono le
    # controparti conversazionali non-reasoning: accettano temperature e non
    # spendono token in ragionamento.
    if "chat" in name:
        return STANDARD_STYLE
    return REASONING_STYLE if name.startswith(REASONING_PREFIXES) else STANDARD_STYLE


def adapt_style(style: CallStyle, error: str) -> CallStyle | None:
    """Legge l'errore dell'API e propone uno stile corretto, o None se non c'entra.

    È la parte che rende il client indipendente dal catalogo dei modelli: un
    deployment che rifiuta un parametro lo dice nel messaggio d'errore, e noi ci
    adeguiamo senza bisogno di una nuova release.
    """
    message = error.lower()

    if style.token_param == "max_tokens" and "max_completion_tokens" in message:
        return replace(style, token_param="max_completion_tokens")
    if (
        style.token_param == "max_completion_tokens"
        and "max_completion_tokens" in message
        and ("unsupported" in message or "unrecognized" in message)
    ):
        return replace(style, token_param="max_tokens")

    if style.supports_temperature and "temperature" in message:
        return replace(style, supports_temperature=False)

    if style.send_reasoning_effort and "reasoning_effort" in message:
        return replace(style, send_reasoning_effort=False)

    if style.system_role == "system" and "developer" in message:
        return replace(style, system_role="developer")
    if style.system_role == "developer" and (
        "developer" in message or "system" in message
    ):
        # Il modello non conosce nemmeno il ruolo developer: il testo di sistema
        # finirà dentro il messaggio utente (vedi build_messages).
        return replace(style, system_role="merged")

    return None


def build_messages(style: CallStyle, system: str, user: str) -> list[dict[str, str]]:
    if style.system_role == "merged":
        return [{"role": "user", "content": f"{system}\n\n---\n\n{user}"}]
    return [
        {"role": style.system_role, "content": system},
        {"role": "user", "content": user},
    ]


class AIUnavailableError(RuntimeError):
    """Sollevata quando si chiede una generazione ma l'AI non e' configurata."""


class AIClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any = None
        self._init_error: str = ""
        # Lo stile si impara una volta sola e resta: le chiamate successive non
        # ripagano il costo delle richieste rifiutate.
        self._style: CallStyle = guess_style(
            self.settings.azure_openai_deployment, self.settings.ai_model_family
        )

    # --- ciclo di vita ------------------------------------------------------

    @property
    def available(self) -> bool:
        return self.settings.ai_configured and not self._init_error

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.settings.ai_configured:
            raise AIUnavailableError(
                "AI non configurata: imposta AZURE_OPENAI_ENDPOINT e AZURE_OPENAI_DEPLOYMENT"
            )
        try:
            from openai import AsyncAzureOpenAI

            kwargs: dict[str, Any] = {
                "azure_endpoint": self.settings.azure_openai_endpoint,
                "api_version": self.settings.azure_openai_api_version,
                "timeout": self.settings.ai_request_timeout_seconds,
                "max_retries": 2,
            }
            if self.settings.azure_openai_api_key:
                kwargs["api_key"] = self.settings.azure_openai_api_key
            else:
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider

                kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
                    DefaultAzureCredential(), _TOKEN_SCOPE
                )
            self._client = AsyncAzureOpenAI(**kwargs)
        except AIUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - dipende dall'ambiente
            self._init_error = str(exc)
            logger.exception("Inizializzazione del client AI fallita")
            raise AIUnavailableError(f"Client AI non inizializzabile: {exc}") from exc
        return self._client

    # --- chiamate -----------------------------------------------------------

    @property
    def style(self) -> CallStyle:
        """Stile attualmente in uso. Esposto per diagnostica e test."""
        return self._style

    def _kwargs(
        self,
        style: CallStyle,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        budget = max_tokens or (
            self.settings.ai_reasoning_max_output_tokens
            if style.is_reasoning
            else self.settings.ai_max_output_tokens
        )
        kwargs: dict[str, Any] = {
            "model": self.settings.azure_openai_deployment,
            "messages": build_messages(style, system, user),
            style.token_param: budget,
        }
        if style.supports_temperature:
            kwargs["temperature"] = temperature
        if style.send_reasoning_effort and self.settings.ai_reasoning_effort:
            kwargs["reasoning_effort"] = self.settings.ai_reasoning_effort
        return kwargs

    async def _create(
        self,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int | None,
        extra: dict[str, Any],
    ) -> Any:
        """Esegue la chiamata, correggendo lo stile se l'API rifiuta un parametro.

        Solleva l'errore originale se non è riconducibile a un parametro che
        sappiamo negoziare: non ha senso ritentare su una quota esaurita.
        """
        client = self._ensure_client()
        style = self._style
        # Al massimo quattro correzioni: token, temperature, reasoning_effort, ruolo.
        for _ in range(4):
            try:
                response = await client.chat.completions.create(
                    **self._kwargs(style, system, user, temperature, max_tokens), **extra
                )
            except Exception as exc:
                adapted = adapt_style(style, str(exc))
                if adapted is None or adapted == style:
                    raise
                logger.info(
                    "Il deployment ha rifiutato un parametro, adatto lo stile: %s -> %s",
                    style,
                    adapted,
                )
                style = adapted
                continue
            if style != self._style:
                logger.info("Stile di chiamata appreso per questo deployment: %s", style)
                self._style = style
            return response
        raise RuntimeError("Impossibile trovare uno stile di chiamata accettato dal deployment")

    async def complete_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.4,
        max_tokens: int | None = None,
    ) -> str:
        response = await self._create(system, user, temperature, max_tokens, {})
        return (response.choices[0].message.content or "").strip()

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        schema: dict | None = None,
        schema_name: str = "risposta",
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict:
        """Chiede una risposta JSON e la restituisce gia' deserializzata.

        Prova prima gli structured output (json_schema). Se il deployment non li
        supporta ripiega su json_object e, in ultima istanza, sull'estrazione
        del primo oggetto JSON presente nel testo.
        """
        attempts: list[dict[str, Any]] = []
        if schema:
            attempts.append(
                {
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": schema,
                            "strict": False,
                        },
                    }
                }
            )
        attempts.append({"response_format": {"type": "json_object"}})
        attempts.append({})

        last_error: Exception | None = None
        for extra in attempts:
            try:
                response = await self._create(system, user, temperature, max_tokens, extra)
                content = response.choices[0].message.content or ""
                parsed = extract_json(content)
                if parsed is not None:
                    return parsed
                # Un modello reasoning che restituisce vuoto ha quasi sempre
                # consumato tutto il budget in ragionamento: dirlo aiuta.
                last_error = ValueError(
                    "La risposta del modello non conteneva JSON valido"
                    + (
                        " (risposta vuota: prova ad alzare AI_REASONING_MAX_OUTPUT_TOKENS"
                        " o ad abbassare AI_REASONING_EFFORT)"
                        if not content.strip() and self._style.is_reasoning
                        else ""
                    )
                )
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                # Un errore sul formato significa "questo deployment non lo
                # supporta": passiamo al tentativo successivo. Gli altri sono fatali.
                if "response_format" not in message and "json_schema" not in message:
                    raise
                logger.info("response_format non supportato, ripiego sul tentativo successivo")
        raise RuntimeError(f"Chiamata AI fallita: {last_error}")

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:  # pragma: no cover
                pass
            self._client = None


def extract_json(text: str) -> dict | None:
    """Estrae un oggetto JSON da una risposta, tollerando i fence markdown."""
    if not text:
        return None
    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        pass
    # Ultimo tentativo: il primo blocco bilanciato da { a }.
    start = candidate.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(candidate)):
        char = candidate[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(candidate[start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


_client_lock = asyncio.Lock()
_singleton: AIClient | None = None


async def get_ai_client() -> AIClient:
    global _singleton
    async with _client_lock:
        if _singleton is None:
            _singleton = AIClient()
    return _singleton
