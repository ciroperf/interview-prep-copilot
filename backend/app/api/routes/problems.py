"""Problemi di coding: elenco, dettaglio e revisione della soluzione."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...deps import AccessGuard, CodingServiceDep, KnowledgeDep, RepositoryDep
from ...domain.models import CodeSubmission, JobPosting

router = APIRouter(prefix="/problems", tags=["coding"], dependencies=[AccessGuard])


@router.get("")
async def list_problems(
    kb: KnowledgeDep,
    service: CodingServiceDep,
    repo: RepositoryDep,
    job_id: str | None = None,
    difficulty: str | None = None,
    limit: int = 30,
) -> dict:
    if job_id:
        raw = repo.get("jobs", job_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Annuncio non trovato")
        problems = service.recommend(JobPosting(**raw), limit=limit)
    else:
        problems = list(kb.problems.values())

    if difficulty:
        problems = [p for p in problems if p.difficulty == difficulty]

    return {
        "total": len(problems),
        "problems": [
            {
                "id": p.id,
                "title": p.title,
                "difficulty": p.difficulty,
                "tags": p.tags,
                "estimated_minutes": p.estimated_minutes,
                "target_complexity": p.target_complexity,
                "topic_ids": p.topic_ids,
            }
            for p in problems[:limit]
        ],
    }


@router.get("/{problem_id}")
async def get_problem(problem_id: str, kb: KnowledgeDep) -> dict:
    problem = kb.problems.get(problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problema non trovato")
    return {"problem": problem.public()}


@router.post("/{problem_id}/submit")
async def submit_solution(
    problem_id: str,
    payload: CodeSubmission,
    kb: KnowledgeDep,
    service: CodingServiceDep,
    repo: RepositoryDep,
) -> dict:
    problem = kb.problems.get(problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problema non trovato")
    if payload.problem_id != problem_id:
        raise HTTPException(status_code=400, detail="problem_id incoerente con la rotta")

    review = await service.review(problem, payload.code)
    repo.put("reviews", review.id, review.model_dump(mode="json"))
    return {"review": review.model_dump(mode="json")}


@router.get("/{problem_id}/solution")
async def get_solution(problem_id: str, kb: KnowledgeDep) -> dict:
    """La soluzione di riferimento è esposta su una rotta separata, per scelta:
    non deve arrivare al client insieme al testo del problema."""
    problem = kb.problems.get(problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problema non trovato")
    return {"solution": problem.solution, "target_complexity": problem.target_complexity}
