"""Ampliamento della knowledge base a partire dagli annunci analizzati.

Il catalogo versionato nel repository non può coprire tutto. Quando un annuncio
chiede una competenza che non ha un argomento dedicato (es. Kubernetes), qui la
si genera, la si persiste e la si registra nell'indice: da quel momento entra nei
piani, nei quiz e nella ricerca come qualunque altro argomento.

I contenuti aggiunti vivono nello storage, non nei file YAML. L'export li
restituisce già nel formato di `app/content/`, così possono essere committati nel
repository e diventare parte del catalogo stabile.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

from ..ai import prompts
from ..ai.client import AIClient
from ..domain.models import (
    JobPosting,
    QuizQuestion,
    Topic,
    TopicCreate,
    TopicGap,
    new_id,
    utcnow,
)
from ..storage.base import Repository
from .knowledge import KnowledgeBase

logger = logging.getLogger(__name__)

CUSTOM_COLLECTION = "custom_topics"

# Termini troppo generici per meritare un argomento dedicato.
IGNORED_TERMS = {
    "agile", "scrum", "kanban", "git", "rest", "api", "backend", "frontend",
    "problem solving", "teamwork", "inglese", "english", "comunicazione",
    "laurea", "informatica", "ingegneria",
}


class KnowledgeCurator:
    def __init__(self, kb: KnowledgeBase, ai: AIClient, repo: Repository) -> None:
        self.kb = kb
        self.ai = ai
        self.repo = repo

    # --- rilevamento delle lacune -------------------------------------------

    def find_gaps(self, posting: JobPosting, limit: int = 12) -> list[TopicGap]:
        """Competenze richieste dall'annuncio senza un argomento dedicato."""
        candidates: dict[str, int] = {}
        for requirement in posting.requirements:
            name = requirement.name.strip()
            if name:
                candidates[name] = max(candidates.get(name, 0), requirement.importance)
        for tech in posting.tech_stack:
            name = tech.strip()
            if name:
                candidates.setdefault(name, 3)

        gaps: list[TopicGap] = []
        for term, importance in candidates.items():
            if term.lower() in IGNORED_TERMS:
                continue
            score, topic_id, dedicated = self.kb.coverage(term)
            gaps.append(
                TopicGap(
                    term=term,
                    importance=importance,
                    covered=dedicated,
                    coverage_score=round(score, 1),
                    best_topic_id=topic_id,
                    best_topic_title=self.kb.topics[topic_id].title if topic_id else "",
                )
            )
        # Prima le lacune, e fra queste le più richieste dall'annuncio.
        gaps.sort(key=lambda g: (g.covered, -g.importance, g.coverage_score))
        return gaps[:limit]

    # --- creazione di un argomento ------------------------------------------

    async def create_topic(
        self, request: TopicCreate, posting: JobPosting | None = None
    ) -> tuple[Topic, list[QuizQuestion]]:
        topic_id = self.kb.slugify(request.term)

        if request.draft is not None:
            topic = self._from_draft(topic_id, request)
            questions: list[QuizQuestion] = []
        else:
            if not self.ai.available:
                raise ValueError(
                    "Per generare un argomento serve un modello AI configurato. "
                    "In alternativa invia il contenuto nel campo 'draft'."
                )
            topic, questions = await self._from_ai(topic_id, request, posting)

        self.kb.register_topic(topic, questions)
        self.repo.put(
            CUSTOM_COLLECTION,
            topic.id,
            {
                "topic": topic.model_dump(mode="json"),
                "questions": [q.model_dump(mode="json") for q in questions],
            },
        )
        logger.info("Argomento aggiunto al catalogo: %s (%d domande)", topic.id, len(questions))
        return topic, questions

    @staticmethod
    def _from_draft(topic_id: str, request: TopicCreate) -> Topic:
        draft = request.draft
        assert draft is not None
        return Topic(
            id=topic_id,
            title=draft.title,
            category=request.category or draft.category,
            track=draft.track,
            level=draft.level,
            tags=draft.tags or [request.term.lower()],
            summary=draft.summary,
            key_points=draft.key_points,
            interview_answer=draft.interview_answer,
            pitfalls=draft.pitfalls,
            follow_up_questions=draft.follow_up_questions,
            estimated_minutes=draft.estimated_minutes,
            custom=True,
            created_at=utcnow(),
            source_term=request.term,
        )

    async def _from_ai(
        self, topic_id: str, request: TopicCreate, posting: JobPosting | None
    ) -> tuple[Topic, list[QuizQuestion]]:
        context = "colloquio tecnico per sviluppatore software"
        if posting:
            context = (
                f"{posting.role_title or 'sviluppatore'} ({posting.seniority})"
                f"{' presso ' + posting.company_name if posting.company_name else ''}. "
                f"Stack dell'annuncio: {', '.join(posting.tech_stack[:10]) or 'non specificato'}"
            )
        data = await self.ai.complete_json(
            prompts.TOPIC_SYSTEM,
            prompts.topic_user(request.term, context, request.num_questions),
            schema=prompts.TOPIC_SCHEMA,
            schema_name="nuovo_argomento",
            temperature=0.4,
        )

        def strings(key: str, limit: int, size: int = 400) -> list[str]:
            value = data.get(key)
            return [str(v)[:size] for v in value][:limit] if isinstance(value, list) else []

        level = str(data.get("level", "medium"))
        track = str(data.get("track", "knowledge"))
        topic = Topic(
            id=topic_id,
            title=str(data.get("title") or request.term)[:120],
            category=request.category or str(data.get("category") or "custom")[:40],
            track=track if track in {"knowledge", "technical"} else "knowledge",  # type: ignore
            level=level if level in {"easy", "medium", "hard"} else "medium",  # type: ignore
            tags=[str(t)[:40] for t in (data.get("tags") or [])][:8] or [request.term.lower()],
            summary=str(data.get("summary", ""))[:2000],
            deep_dive=str(data.get("deep_dive", ""))[:8000],
            key_points=strings("key_points", 10),
            interview_answer=str(data.get("interview_answer", ""))[:3000],
            pitfalls=strings("pitfalls", 6),
            follow_up_questions=strings("follow_up_questions", 5),
            estimated_minutes=self._as_minutes(data.get("estimated_minutes")),
            custom=True,
            created_at=utcnow(),
            source_term=request.term,
        )
        if not topic.summary:
            raise ValueError("Il modello non ha prodotto un contenuto utilizzabile")

        questions = self._parse_questions(data.get("questions"), topic.id, request.num_questions)
        return topic, questions

    @staticmethod
    def _as_minutes(value: Any) -> int:
        try:
            return max(5, min(240, int(value)))
        except (TypeError, ValueError):
            return 30

    @staticmethod
    def _parse_questions(raw: Any, topic_id: str, limit: int) -> list[QuizQuestion]:
        if not isinstance(raw, list) or limit <= 0:
            return []
        out: list[QuizQuestion] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            options = row.get("options")
            if not isinstance(options, list) or len(options) != 4:
                continue
            try:
                answer_index = int(row.get("answer_index", -1))
            except (TypeError, ValueError):
                continue
            if not 0 <= answer_index < 4:
                continue
            difficulty = str(row.get("difficulty", "medium"))
            out.append(
                QuizQuestion(
                    id=new_id("cq"),
                    topic_id=topic_id,
                    prompt=str(row.get("prompt", ""))[:1000],
                    options=[str(o)[:500] for o in options],
                    answer_index=answer_index,
                    explanation=str(row.get("explanation", ""))[:1500],
                    difficulty=difficulty if difficulty in {"easy", "medium", "hard"} else "medium",  # type: ignore
                    generated=True,
                )
            )
            if len(out) >= limit:
                break
        return out

    # --- gestione -----------------------------------------------------------

    def delete_topic(self, topic_id: str) -> bool:
        if not self.kb.remove_topic(topic_id):
            return False
        self.repo.delete(CUSTOM_COLLECTION, topic_id)
        return True

    def load_persisted(self) -> int:
        """Richiamata all'avvio: rimette nell'indice gli argomenti già creati."""
        try:
            rows = self.repo.list(CUSTOM_COLLECTION, limit=500)
        except Exception as exc:
            logger.warning("Argomenti personalizzati non caricabili: %s", exc)
            return 0
        return self.kb.load_custom(rows)

    # --- export nel formato del repository ----------------------------------

    def export(self) -> dict[str, Any]:
        """Restituisce gli argomenti aggiunti nel formato dei file di `app/content/`.

        Serve a rendere permanente ciò che oggi vive solo nello storage: si
        scaricano i due file, si mettono in `backend/app/content/` e si committano.
        """
        topics = self.kb.custom_topics()
        topic_rows = []
        question_rows = []
        for topic in topics:
            data = topic.model_dump(mode="json", exclude={"custom", "created_at"})
            data.pop("source_term", None)
            # I campi vuoti sporcherebbero il file senza aggiungere informazione.
            topic_rows.append({k: v for k, v in data.items() if v not in ("", [], None)})
            for question_id in self.kb.questions_by_topic.get(topic.id, []):
                question = self.kb.questions[question_id]
                row = question.model_dump(mode="json", exclude={"generated"})
                question_rows.append({k: v for k, v in row.items() if v not in ("", [], None)})

        header = (
            "# Argomenti aggiunti dall'app a partire dagli annunci analizzati.\n"
            "# Copia questo file in backend/app/content/ e committalo per renderlo stabile.\n"
        )
        dump = lambda rows: yaml.safe_dump(  # noqa: E731
            rows, allow_unicode=True, sort_keys=False, default_flow_style=False, width=100
        )
        return {
            "count": len(topic_rows),
            "question_count": len(question_rows),
            "topics_yaml": header + (dump(topic_rows) if topic_rows else ""),
            "questions_yaml": header + (dump(question_rows) if question_rows else ""),
        }
