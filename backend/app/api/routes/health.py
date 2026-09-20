"""Health check e metadati di configurazione."""

from __future__ import annotations

from fastapi import APIRouter

from ...ai.client import guess_style
from ...deps import KnowledgeDep, SettingsDep

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
        "access_code_required": bool(settings.access_code),
        "storage_backend": settings.storage_backend,
        "content": {
            "topics": len(kb.topics),
            "questions": len(kb.questions),
            "problems": len(kb.problems),
            "categories": kb.categories,
        },
    }
