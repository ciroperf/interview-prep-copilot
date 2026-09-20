"""Piani di studio: generazione, consultazione, avanzamento."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...deps import AccessGuard, PlanBuilderDep, RepositoryDep
from ...domain.models import PlanItemUpdate, StudyPlan, StudyPlanCreate, utcnow
from ...services.planner import plan_by_day, plan_progress_by_track
from .jobs import load_job

router = APIRouter(prefix="/plans", tags=["piani"], dependencies=[AccessGuard])


def _load_plan(repo, plan_id: str) -> StudyPlan:
    raw = repo.get("plans", plan_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Piano non trovato")
    return StudyPlan(**raw)


def _serialize(plan: StudyPlan) -> dict:
    return {
        "plan": plan.model_dump(mode="json"),
        "progress": plan.progress(),
        "by_track": plan_progress_by_track(plan),
        "by_day": plan_by_day(plan),
    }


@router.post("", status_code=201)
async def create_plan(
    payload: StudyPlanCreate,
    builder: PlanBuilderDep,
    repo: RepositoryDep,
) -> dict:
    posting = load_job(repo, payload.job_id)
    plan = await builder.build(posting, payload)
    repo.put("plans", plan.id, plan.model_dump(mode="json"))
    return _serialize(plan)


@router.get("")
async def list_plans(repo: RepositoryDep, job_id: str | None = None, limit: int = 50) -> dict:
    rows = repo.list("plans", limit=limit)
    if job_id:
        rows = [row for row in rows if row.get("job_id") == job_id]
    out = []
    for row in rows:
        plan = StudyPlan(**row)
        out.append(
            {
                "id": plan.id,
                "job_id": plan.job_id,
                "title": plan.title,
                "created_at": plan.created_at.isoformat(),
                "interview_date": plan.interview_date.isoformat()
                if plan.interview_date
                else None,
                "days": plan.days,
                "daily_minutes": plan.daily_minutes,
                "ai_generated": plan.ai_generated,
                "progress": plan.progress(),
            }
        )
    return {"total": len(out), "plans": out}


@router.get("/{plan_id}")
async def get_plan(plan_id: str, repo: RepositoryDep) -> dict:
    return _serialize(_load_plan(repo, plan_id))


@router.patch("/{plan_id}/items/{item_id}")
async def update_item(
    plan_id: str, item_id: str, payload: PlanItemUpdate, repo: RepositoryDep
) -> dict:
    plan = _load_plan(repo, plan_id)
    for item in plan.items:
        if item.id == item_id:
            item.status = payload.status
            item.completed_at = utcnow() if payload.status == "done" else None
            repo.put("plans", plan.id, plan.model_dump(mode="json"))
            return {
                "item": item.model_dump(mode="json"),
                "progress": plan.progress(),
                "by_track": plan_progress_by_track(plan),
            }
    raise HTTPException(status_code=404, detail="Attività non trovata nel piano")


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(plan_id: str, repo: RepositoryDep) -> None:
    if not repo.delete("plans", plan_id):
        raise HTTPException(status_code=404, detail="Piano non trovato")
