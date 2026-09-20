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
from typing import Any

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


class AIUnavailableError(RuntimeError):
    """Sollevata quando si chiede una generazione ma l'AI non e' configurata."""


class AIClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any = None
        self._init_error: str = ""

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

    async def complete_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.4,
        max_tokens: int | None = None,
    ) -> str:
        client = self._ensure_client()
        response = await client.chat.completions.create(
            model=self.settings.azure_openai_deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens or self.settings.ai_max_output_tokens,
        )
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
        client = self._ensure_client()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        base: dict[str, Any] = {
            "model": self.settings.azure_openai_deployment,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.settings.ai_max_output_tokens,
        }

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
                response = await client.chat.completions.create(**base, **extra)
                content = response.choices[0].message.content or ""
                parsed = extract_json(content)
                if parsed is not None:
                    return parsed
                last_error = ValueError("La risposta del modello non conteneva JSON valido")
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                # Un errore di formato significa "questo deployment non lo supporta":
                # passiamo al tentativo successivo. Gli altri errori sono fatali.
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
