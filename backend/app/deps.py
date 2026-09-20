"""Dipendenze condivise dalle rotte FastAPI."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from .ai.client import AIClient, get_ai_client
from .config import Settings, get_settings
from .services.coding import CodingService
from .services.curator import KnowledgeCurator
from .services.cv import CvService
from .services.jobs import JobAnalyzer
from .services.knowledge import KnowledgeBase, get_knowledge_base
from .services.planner import StudyPlanBuilder
from .services.quiz import QuizService
from .storage.base import BlobStore, Repository
from .storage.factory import get_blob_store, get_repository

SettingsDep = Annotated[Settings, Depends(get_settings)]
KnowledgeDep = Annotated[KnowledgeBase, Depends(get_knowledge_base)]
RepositoryDep = Annotated[Repository, Depends(get_repository)]
BlobStoreDep = Annotated[BlobStore, Depends(get_blob_store)]
AIDep = Annotated[AIClient, Depends(get_ai_client)]


async def require_access(
    settings: SettingsDep,
    x_access_code: Annotated[str | None, Header(alias="X-Access-Code")] = None,
) -> None:
    """Protezione a codice condiviso: l'app è pensata per un singolo utente.

    Se `access_code` è vuoto l'API resta aperta, cosa accettabile solo in locale.
    In Azure il codice viene sempre impostato dal Terraform.
    """
    expected = settings.access_code
    if not expected:
        return
    # Confronto a tempo costante: evita di far dedurre il codice dai tempi di risposta.
    if not x_access_code or not hmac.compare_digest(x_access_code, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Codice di accesso mancante o errato",
            headers={"WWW-Authenticate": "AccessCode"},
        )


AccessGuard = Depends(require_access)


def get_job_analyzer(ai: AIDep) -> JobAnalyzer:
    return JobAnalyzer(ai)


def get_plan_builder(kb: KnowledgeDep, ai: AIDep) -> StudyPlanBuilder:
    return StudyPlanBuilder(kb, ai)


def get_quiz_service(kb: KnowledgeDep, ai: AIDep) -> QuizService:
    return QuizService(kb, ai)


def get_coding_service(kb: KnowledgeDep, ai: AIDep, settings: SettingsDep) -> CodingService:
    return CodingService(kb, ai, settings)


def get_cv_service(ai: AIDep) -> CvService:
    return CvService(ai)


def get_curator(kb: KnowledgeDep, ai: AIDep, repo: RepositoryDep) -> KnowledgeCurator:
    return KnowledgeCurator(kb, ai, repo)


JobAnalyzerDep = Annotated[JobAnalyzer, Depends(get_job_analyzer)]
PlanBuilderDep = Annotated[StudyPlanBuilder, Depends(get_plan_builder)]
QuizServiceDep = Annotated[QuizService, Depends(get_quiz_service)]
CodingServiceDep = Annotated[CodingService, Depends(get_coding_service)]
CvServiceDep = Annotated[CvService, Depends(get_cv_service)]
CuratorDep = Annotated[KnowledgeCurator, Depends(get_curator)]
