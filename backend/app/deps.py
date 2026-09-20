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
    principal_id: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-ID")
    ] = None,
    principal_name: Annotated[
        str | None, Header(alias="X-MS-CLIENT-PRINCIPAL-NAME")
    ] = None,
) -> None:
    """Verifica che chi chiama abbia diritto di farlo, nel modo configurato.

    Con `entra_id` la validazione del token è già avvenuta: l'autenticazione
    integrata di Container Apps sta davanti all'applicazione, rifiuta da sé le
    richieste senza un Bearer valido e inietta l'identità negli header
    X-MS-CLIENT-PRINCIPAL-*. Questi header sono affidabili perché quel livello
    rimuove quelli eventualmente inviati dal client; qui si controlla solo che
    ci siano, il che copre il caso di una configurazione incompleta.

    Con `access_code` si confronta un codice condiviso. Se è vuoto l'API resta
    aperta: accettabile solo in locale.
    """
    if settings.auth_mode == "entra_id":
        if not (principal_id or principal_name):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Autenticazione Microsoft richiesta. Se vedi questo errore da "
                    "un'applicazione già autenticata, l'autenticazione integrata "
                    "della Container App non è attiva."
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )
        return

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
