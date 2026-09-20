"""Quiz a risposta multipla: generazione e correzione."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...deps import AccessGuard, KnowledgeDep, QuizServiceDep, RepositoryDep
from ...domain.models import Quiz, QuizCreate, QuizSubmission

router = APIRouter(prefix="/quizzes", tags=["quiz"], dependencies=[AccessGuard])


def _load_quiz(repo, quiz_id: str) -> Quiz:
    raw = repo.get("quizzes", quiz_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Quiz non trovato")
    return Quiz(**raw)


def _public_view(quiz: Quiz, kb) -> dict:
    """Vista senza soluzioni: è ciò che riceve il client prima di rispondere."""
    return {
        "id": quiz.id,
        "job_id": quiz.job_id,
        "plan_id": quiz.plan_id,
        "created_at": quiz.created_at.isoformat(),
        "submitted": quiz.submitted_at is not None,
        "questions": [
            {
                **q.public().model_dump(),
                "topic_title": kb.topics[q.topic_id].title if q.topic_id in kb.topics else "",
            }
            for q in quiz.questions
        ],
    }


@router.post("", status_code=201)
async def create_quiz(
    payload: QuizCreate,
    service: QuizServiceDep,
    repo: RepositoryDep,
    kb: KnowledgeDep,
) -> dict:
    posting = None
    if payload.job_id:
        raw = repo.get("jobs", payload.job_id)
        if raw is None:
            raise HTTPException(status_code=404, detail="Annuncio non trovato")
        from ...domain.models import JobPosting

        posting = JobPosting(**raw)

    quiz = await service.build(payload, posting)
    if not quiz.questions:
        raise HTTPException(
            status_code=422,
            detail="Nessuna domanda disponibile per gli argomenti richiesti",
        )
    repo.put("quizzes", quiz.id, quiz.model_dump(mode="json"))
    return _public_view(quiz, kb)


@router.get("/{quiz_id}")
async def get_quiz(quiz_id: str, repo: RepositoryDep, kb: KnowledgeDep) -> dict:
    quiz = _load_quiz(repo, quiz_id)
    view = _public_view(quiz, kb)
    if quiz.submitted_at:
        view["result"] = _result_view(quiz, kb)
    return view


@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: str,
    payload: QuizSubmission,
    service: QuizServiceDep,
    repo: RepositoryDep,
    kb: KnowledgeDep,
) -> dict:
    quiz = _load_quiz(repo, quiz_id)
    if quiz.submitted_at:
        raise HTTPException(status_code=409, detail="Quiz già consegnato")
    quiz = service.grade(quiz, payload)
    repo.put("quizzes", quiz.id, quiz.model_dump(mode="json"))
    return _result_view(quiz, kb)


def _result_view(quiz: Quiz, kb) -> dict:
    return {
        "id": quiz.id,
        "score": quiz.score,
        "correct": sum(1 for g in quiz.graded if g.correct),
        "total": len(quiz.graded),
        "submitted_at": quiz.submitted_at.isoformat() if quiz.submitted_at else None,
        "answers": [
            {
                **g.model_dump(),
                "options": next(
                    (q.options for q in quiz.questions if q.id == g.question_id), []
                ),
                "topic_title": kb.topics[g.topic_id].title if g.topic_id in kb.topics else "",
            }
            for g in quiz.graded
        ],
        "weak_topics": [
            {"id": tid, "title": kb.topics[tid].title}
            for tid in quiz.weak_topics
            if tid in kb.topics
        ],
    }


@router.get("")
async def list_quizzes(repo: RepositoryDep, limit: int = 30) -> dict:
    rows = repo.list("quizzes", limit=limit)
    return {
        "total": len(rows),
        "quizzes": [
            {
                "id": row.get("id"),
                "job_id": row.get("job_id"),
                "created_at": row.get("created_at"),
                "submitted_at": row.get("submitted_at"),
                "score": row.get("score"),
                "question_count": len(row.get("questions", [])),
            }
            for row in rows
        ],
    }
