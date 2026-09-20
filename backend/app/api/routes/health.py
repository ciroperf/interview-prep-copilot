"""Health check e metadati di configurazione."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from ...ai.client import guess_style
from ...deps import AccessGuard, AIDep, KnowledgeDep, SettingsDep

router = APIRouter(tags=["sistema"])


@router.get("/health")
async def health() -> dict:
    """Usato da Container Apps come probe: deve restare leggero e senza I/O."""
    return {"status": "ok"}


@router.get("/meta")
async def meta(settings: SettingsDep, kb: KnowledgeDep) -> dict:
    """Cosa è attivo su questa istanza: il frontend ci adatta la UI."""
    # Lo stile di chiamata è l'ipotesi iniziale: dopo la prima generazione il
    # client può averlo corretto leggendo l'errore del deployment.
    style = guess_style(settings.azure_openai_deployment, settings.ai_model_family)
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "ai_enabled": settings.ai_configured,
        "ai_deployment": settings.azure_openai_deployment if settings.ai_configured else "",
        "ai_auth": "managed_identity" if settings.uses_managed_identity else "api_key",
        "ai_api_version": settings.azure_openai_api_version if settings.ai_configured else "",
        "ai_family": "reasoning" if style.is_reasoning else "standard",
        "ai_reasoning_effort": settings.ai_reasoning_effort,
        "ai_max_output_tokens": (
            settings.ai_reasoning_max_output_tokens
            if style.is_reasoning
            else settings.ai_max_output_tokens
        ),
        "code_execution_enabled": settings.enable_code_execution,
        "auth_mode": settings.auth_mode,
        "access_code_required": (
            settings.auth_mode == "access_code" and bool(settings.access_code)
        ),
        "storage_backend": settings.storage_backend,
        "content": {
            "topics": len(kb.topics),
            "questions": len(kb.questions),
            "problems": len(kb.problems),
            "categories": kb.categories,
        },
    }


@router.post("/ai/selftest", dependencies=[AccessGuard], tags=["sistema"])
async def ai_selftest(ai: AIDep, settings: SettingsDep) -> dict:
    """Esegue una generazione minima e riferisce cosa ha funzionato.

    È il modo rapido di verificare che modello, versione dell'API e permessi
    siano a posto dopo un cambio di configurazione, senza dover analizzare un
    annuncio vero. Consuma una manciata di token.
    """
    if not settings.ai_configured:
        raise HTTPException(
            status_code=400,
            detail="AI non configurata: mancano AZURE_OPENAI_ENDPOINT o AZURE_OPENAI_DEPLOYMENT.",
        )

    prima = guess_style(settings.azure_openai_deployment, settings.ai_model_family)
    avvio = time.perf_counter()
    try:
        risposta = await ai.complete_json(
            "Rispondi solo con JSON valido.",
            'Restituisci esattamente questo oggetto: {"ok": true}',
            schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
            schema_name="selftest",
            max_tokens=2000,
        )
    except Exception as exc:
        return {
            "ok": False,
            "deployment": settings.azure_openai_deployment,
            "api_version_configured": settings.azure_openai_api_version,
            "api_version_used": ai.api_version,
            "latency_ms": round((time.perf_counter() - avvio) * 1000),
            "error": str(exc)[:600],
            "hint": _selftest_hint(str(exc)),
        }

    finale = ai.style
    versione_usata = ai.api_version
    cambiata = versione_usata != settings.azure_openai_api_version
    return {
        "ok": True,
        "deployment": settings.azure_openai_deployment,
        "api_version_configured": settings.azure_openai_api_version,
        # Può differire: se il servizio rifiuta quella configurata, il client ne
        # sceglie una fra quelle che il messaggio d'errore elenca.
        "api_version_used": versione_usata,
        "latency_ms": round((time.perf_counter() - avvio) * 1000),
        "family_guessed": "reasoning" if prima.is_reasoning else "standard",
        "family_actual": "reasoning" if finale.is_reasoning else "standard",
        "adapted": finale != prima or cambiata,
        "style": {
            "token_param": finale.token_param,
            "temperature": finale.supports_temperature,
            "system_role": finale.system_role,
            "reasoning_effort": settings.ai_reasoning_effort if finale.is_reasoning else "",
        },
        "response": risposta,
        "hint": _fix_config_hint(settings, finale, prima, versione_usata),
    }


def _fix_config_hint(settings, finale, prima, versione_usata: str) -> str:
    """Suggerisce come rendere stabile ciò che il client ha dovuto scoprire.

    Tutto funziona anche senza seguirlo, ma ogni riavvio ripagherebbe i
    tentativi: fissare i valori li elimina.
    """
    correzioni: list[str] = []
    if versione_usata != settings.azure_openai_api_version:
        correzioni.append(f'ai_api_version = "{versione_usata}"')
    if finale != prima:
        famiglia = "reasoning" if finale.is_reasoning else "standard"
        correzioni.append(f'ai_model_family = "{famiglia}"')
    if not correzioni:
        return "Configurazione corretta: nessun tentativo sprecato."
    return (
        "Funziona, ma il client ha dovuto correggersi. Metti in "
        "terraform.tfvars: " + "; ".join(correzioni)
    )


def _selftest_hint(error: str) -> str:
    """Traduce gli errori più comuni in un'azione concreta."""
    message = error.lower()
    if "max_completion_tokens" in message or "max_tokens" in message:
        return (
            "La versione dell'API non conosce i parametri del modello scelto. "
            "Alza ai_api_version a una preview recente, es. 2025-01-01-preview."
        )
    if "deploymentnotfound" in message or "404" in message:
        return (
            "Il deployment non esiste con quel nome. Controlla con: "
            "az cognitiveservices account deployment list -n <account> -g <rg> -o table"
        )
    if "401" in message or "permission" in message or "forbidden" in message or "403" in message:
        return (
            "Permessi mancanti. La managed identity deve avere il ruolo "
            "Cognitive Services OpenAI User sull'account AI."
        )
    if "429" in message or "quota" in message or "rate" in message:
        return "Quota esaurita: alza ai_capacity oppure aspetta la finestra successiva."
    if "json" in message and "vuota" in message:
        return (
            "Il modello ha consumato il budget in ragionamento. Abbassa "
            "ai_reasoning_effort a low oppure alza AI_REASONING_MAX_OUTPUT_TOKENS."
        )
    return "Controlla i log della Container App per il dettaglio."
