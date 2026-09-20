"""Annunci di lavoro: analisi, elenco, dettaglio."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...deps import AccessGuard, JobAnalyzerDep, RepositoryDep
from ...domain.models import JobPosting, JobPostingCreate

router = APIRouter(prefix="/jobs", tags=["annunci"], dependencies=[AccessGuard])


def load_job(repo, job_id: str) -> JobPosting:
    """Recupera un annuncio o solleva 404. Riusata dalle altre rotte."""
    raw = repo.get("jobs", job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
    return JobPosting(**raw)


@router.post("", status_code=201)
async def create_job(
    payload: JobPostingCreate,
    analyzer: JobAnalyzerDep,
    repo: RepositoryDep,
) -> dict:
    """Analizza il testo dell'annuncio e ne salva la versione strutturata."""
    posting = await analyzer.analyze(
        payload.raw_text,
        source_url=payload.source_url,
        company_name=payload.company_name,
        notes=payload.notes,
    )
    if payload.research_company:
        posting.company = await analyzer.research_company(posting)

    repo.put("jobs", posting.id, posting.model_dump(mode="json"))
    return {"job": posting.model_dump(mode="json")}


@router.get("")
async def list_jobs(repo: RepositoryDep, limit: int = 50) -> dict:
    rows = repo.list("jobs", limit=limit)
    return {
        "total": len(rows),
        "jobs": [
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "role_title": row.get("role_title"),
                "company_name": row.get("company_name"),
                "seniority": row.get("seniority"),
                "location": row.get("location"),
                "work_mode": row.get("work_mode"),
                "tech_stack": row.get("tech_stack", []),
                "analyzed_with_ai": row.get("analyzed_with_ai", False),
            }
            for row in rows
        ],
    }


@router.get("/{job_id}")
async def get_job(job_id: str, repo: RepositoryDep) -> dict:
    return {"job": load_job(repo, job_id).model_dump(mode="json")}


@router.post("/{job_id}/company")
async def refresh_company(
    job_id: str, analyzer: JobAnalyzerDep, repo: RepositoryDep
) -> dict:
    """Rigenera la scheda azienda senza rianalizzare tutto l'annuncio."""
    posting = load_job(repo, job_id)
    posting.company = await analyzer.research_company(posting)
    repo.put("jobs", posting.id, posting.model_dump(mode="json"))
    return {"company": posting.company.model_dump(mode="json")}


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str, repo: RepositoryDep) -> None:
    if not repo.delete("jobs", job_id):
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
