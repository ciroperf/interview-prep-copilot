"""Consultazione della knowledge base."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...deps import AccessGuard, CuratorDep, KnowledgeDep, RepositoryDep
from ...domain.models import JobPosting, TopicCreate

router = APIRouter(prefix="/knowledge", tags=["knowledge"], dependencies=[AccessGuard])


@router.get("/categories")
async def list_categories(kb: KnowledgeDep) -> dict:
    counts: dict[str, int] = {}
    for topic in kb.topics.values():
        counts[topic.category] = counts.get(topic.category, 0) + 1
    return {
        "categories": [
            {"id": name, "count": counts[name]} for name in sorted(counts)
        ]
    }


@router.get("/topics")
async def list_topics(
    kb: KnowledgeDep,
    category: str | None = None,
    track: str | None = Query(default=None, pattern="^(knowledge|technical)$"),
    q: str | None = None,
) -> dict:
    topics = kb.list_topics(category=category, track=track, query=q)
    return {
        "total": len(topics),
        "topics": [
            {
                "id": t.id,
                "title": t.title,
                "category": t.category,
                "track": t.track,
                "level": t.level,
                "tags": t.tags,
                "summary": t.summary,
                "estimated_minutes": t.estimated_minutes,
                "question_count": len(kb.questions_by_topic.get(t.id, [])),
                "problem_count": len(kb.problems_by_topic.get(t.id, [])),
            }
            for t in topics
        ],
    }


@router.get("/topics/{topic_id}")
async def get_topic(topic_id: str, kb: KnowledgeDep) -> dict:
    topic = kb.topics.get(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Argomento non trovato")
    return {
        "topic": topic.model_dump(),
        "question_count": len(kb.questions_by_topic.get(topic_id, [])),
        "problems": [
            {"id": p.id, "title": p.title, "difficulty": p.difficulty}
            for p in kb.problems_for([topic_id])
        ],
    }


# ---------------------------------------------------------------------------
# Ampliamento del catalogo a partire dagli annunci
# ---------------------------------------------------------------------------


@router.get("/gaps")
async def find_gaps(job_id: str, curator: CuratorDep, repo: RepositoryDep) -> dict:
    """Competenze richieste dall'annuncio che non hanno un argomento dedicato."""
    raw = repo.get("jobs", job_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Annuncio non trovato")
    gaps = curator.find_gaps(JobPosting(**raw))
    return {
        "job_id": job_id,
        "gaps": [g.model_dump() for g in gaps],
        "missing": sum(1 for g in gaps if not g.covered),
    }


@router.post("/topics", status_code=201)
async def create_topic(
    payload: TopicCreate, curator: CuratorDep, repo: RepositoryDep
) -> dict:
    """Aggiunge un argomento al catalogo, generandolo con l'AI o da un contenuto fornito."""
    posting = None
    if payload.job_id:
        raw = repo.get("jobs", payload.job_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Annuncio non trovato")
        posting = JobPosting(**raw)

    topic, questions = await curator.create_topic(payload, posting)
    return {
        "topic": topic.model_dump(mode="json"),
        "question_count": len(questions),
    }


@router.delete("/topics/{topic_id}", status_code=204)
async def delete_topic(topic_id: str, curator: CuratorDep, kb: KnowledgeDep) -> None:
    if topic_id not in kb.topics:
        raise HTTPException(status_code=404, detail="Argomento non trovato")
    if not curator.delete_topic(topic_id):
        raise HTTPException(
            status_code=409,
            detail="Gli argomenti del repository non si eliminano da qui: "
            "modifica i file YAML in backend/app/content/.",
        )


@router.get("/export")
async def export_custom(curator: CuratorDep) -> dict:
    """Esporta gli argomenti aggiunti nel formato dei file di app/content/.

    Serve a rendere permanente nel repository ciò che oggi vive solo nello storage.
    """
    return curator.export()
