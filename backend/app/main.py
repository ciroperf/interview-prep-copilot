"""Punto di ingresso dell'API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .ai.client import get_ai_client
from .api.router import api_router
from .config import get_settings
from .services.curator import KnowledgeCurator
from .services.knowledge import get_knowledge_base
from .storage.factory import get_repository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Caricare la knowledge base all'avvio evita che la prima richiesta paghi
    # il parsing degli YAML: conta su Container Apps, dove si parte da zero repliche.
    kb = get_knowledge_base()
    # Gli argomenti aggiunti dagli annunci vivono nello storage: vanno rimessi
    # nell'indice a ogni avvio, altrimenti sparirebbero al primo riavvio del container.
    try:
        KnowledgeCurator(kb, await get_ai_client(), get_repository()).load_persisted()
    except Exception as exc:
        logger.warning("Argomenti personalizzati non caricati: %s", exc)
    logger.info(
        "Avvio %s (%s): %d argomenti, AI %s",
        settings.app_name,
        settings.environment,
        len(kb.topics),
        "attiva" if settings.ai_configured else "non configurata",
    )
    yield
    client = await get_ai_client()
    await client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "API per la preparazione ai colloqui da software developer: analisi "
            "dell'annuncio, piano di studi su misura, quiz, problemi di coding e "
            "revisione del CV."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Access-Code"],
    )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        # I servizi sollevano ValueError per input non validi: traduciamolo in 400
        # invece di lasciare che diventi un 500 opaco.
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"name": settings.app_name, "docs": "/docs", "api": "/api/meta"}

    return app


app = create_app()
