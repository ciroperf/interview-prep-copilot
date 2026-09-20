"""Caricamento e revisione del CV."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...deps import AccessGuard, BlobStoreDep, CvServiceDep, RepositoryDep, SettingsDep
from ...domain.models import CvReview, JobPosting
from ...services.cv import CvExtractionError, extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["cv"], dependencies=[AccessGuard])


@router.post("/review", status_code=201)
async def review_cv(
    service: CvServiceDep,
    repo: RepositoryDep,
    blobs: BlobStoreDep,
    settings: SettingsDep,
    file: UploadFile = File(..., description="CV in PDF, DOCX, TXT o MD"),
    job_id: str = Form(default=""),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File vuoto")
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / 1024 / 1024
        raise HTTPException(
            status_code=413, detail=f"File troppo grande: massimo {limit_mb:.0f} MB"
        )

    try:
        text = extract_text(file.filename or "cv.txt", data)
    except CvExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if len(text.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail="Il testo estratto è troppo corto per essere un CV.",
        )

    posting = None
    if job_id:
        raw = repo.get("jobs", job_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Annuncio non trovato")
        posting = JobPosting(**raw)

    review = await service.review(text, posting, filename=file.filename or "")

    # Il file si conserva solo se esplicitamente richiesto: di default teniamo
    # in memoria il minimo indispensabile e nessun documento personale a riposo.
    if settings.store_cv_files:
        try:
            review.blob_path = blobs.put_bytes(
                f"{review.id}/{file.filename or 'cv'}",
                data,
                file.content_type or "application/octet-stream",
            )
        except Exception as exc:
            logger.warning("Salvataggio del CV non riuscito: %s", exc)

    repo.put("cv_reviews", review.id, review.model_dump(mode="json"))
    return {"review": review.model_dump(mode="json")}


@router.get("")
async def list_reviews(repo: RepositoryDep, limit: int = 30) -> dict:
    rows = repo.list("cv_reviews", limit=limit)
    return {
        "total": len(rows),
        "reviews": [
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "job_id": row.get("job_id"),
                "filename": row.get("filename"),
                "overall_score": row.get("overall_score"),
                "ai_generated": row.get("ai_generated", False),
            }
            for row in rows
        ],
    }


@router.get("/{review_id}")
async def get_review(review_id: str, repo: RepositoryDep) -> dict:
    raw = repo.get("cv_reviews", review_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Revisione non trovata")
    return {"review": CvReview(**raw).model_dump(mode="json")}


@router.delete("/{review_id}", status_code=204)
async def delete_review(review_id: str, repo: RepositoryDep, blobs: BlobStoreDep) -> None:
    raw = repo.get("cv_reviews", review_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Revisione non trovata")
    blob_path = raw.get("blob_path")
    if blob_path:
        # Il path salvato include il container: per la cancellazione serve la parte relativa.
        relative = blob_path.split("/", 1)[-1] if "/" in blob_path else blob_path
        try:
            blobs.delete(relative)
        except Exception as exc:
            logger.warning("Cancellazione del file CV non riuscita: %s", exc)
    repo.delete("cv_reviews", review_id)
