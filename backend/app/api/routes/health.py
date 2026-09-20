"""Health check e metadati di configurazione."""

from __future__ import annotations

from fastapi import APIRouter

from ...deps import KnowledgeDep, SettingsDep

router = APIRouter(tags=["sistema"])


@router.get("/health")
async def health() -> dict:
    """Usato da Container Apps come probe: deve restare leggero e senza I/O."""
    return {"status": "ok"}


@router.get("/meta")
async def meta(settings: SettingsDep, kb: KnowledgeDep) -> dict:
    """Cosa è attivo su questa istanza: il frontend ci adatta la UI."""
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "ai_enabled": settings.ai_configured,
        "ai_deployment": settings.azure_openai_deployment if settings.ai_configured else "",
        "ai_auth": "managed_identity" if settings.uses_managed_identity else "api_key",
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
