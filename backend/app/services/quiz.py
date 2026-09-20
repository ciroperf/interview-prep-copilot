"""Motore dei quiz a risposta multipla."""

from __future__ import annotations

import logging
import random

from ..ai import prompts
from ..ai.client import AIClient
from ..domain.models import (
    GradedAnswer,
    JobPosting,
    Quiz,
    QuizCreate,
    QuizQuestion,
    QuizSubmission,
    new_id,
    utcnow,
)
from .knowledge import KnowledgeBase

logger = logging.getLogger(__name__)


class QuizService:
    def __init__(self, kb: KnowledgeBase, ai: AIClient) -> None:
        self.kb = kb
        self.ai = ai

    async def build(
        self,
        request: QuizCreate,
        posting: JobPosting | None = None,
        rng: random.Random | None = None,
    ) -> Quiz:
        rng = rng or random.Random()
        topic_ids = request.topic_ids or self._default_topics(posting)

        pool = self.kb.questions_for(topic_ids)
        if request.difficulty:
            filtered = [q for q in pool if q.difficulty == request.difficulty]
            # Se il filtro svuota il pool preferiamo un quiz di difficoltà mista
            # a un quiz vuoto.
            pool = filtered or pool

        rng.shuffle(pool)
        selected = self._spread_across_topics(pool, request.num_questions, rng)

        missing = request.num_questions - len(selected)
        if missing > 0 and request.use_ai and self.ai.available and topic_ids:
            generated = await self._generate(topic_ids, missing, posting, request.difficulty)
            selected.extend(generated)

        # Le opzioni vanno mescolate a ogni quiz: chi scrive le domande tende a
        # mettere la risposta giusta sempre nella stessa posizione, e chi ripete
        # il quiz imparerebbe la posizione invece del concetto.
        shuffled = [self._shuffle_options(q, rng) for q in selected[: request.num_questions]]

        return Quiz(
            job_id=request.job_id,
            plan_id=request.plan_id,
            questions=shuffled,
        )

    @staticmethod
    def _shuffle_options(question: QuizQuestion, rng: random.Random) -> QuizQuestion:
        order = list(range(len(question.options)))
        rng.shuffle(order)
        return question.model_copy(
            update={
                "options": [question.options[i] for i in order],
                # La risposta giusta finisce dove il suo indice originale è stato spostato.
                "answer_index": order.index(question.answer_index),
            }
        )

    def _default_topics(self, posting: JobPosting | None) -> list[str]:
        """Senza argomenti espliciti si parte da quelli pertinenti all'annuncio."""
        if posting is None:
            return list(self.kb.questions_by_topic.keys())
        terms = posting.tech_stack + [r.name for r in posting.requirements]
        scores = self.kb.score_topics(terms) if terms else {}
        ranked = [tid for tid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
        with_questions = [tid for tid in ranked if self.kb.questions_by_topic.get(tid)]
        return with_questions[:12] or list(self.kb.questions_by_topic.keys())

    @staticmethod
    def _spread_across_topics(
        pool: list[QuizQuestion], count: int, rng: random.Random
    ) -> list[QuizQuestion]:
        """Round-robin sugli argomenti, così un solo tema non monopolizza il quiz."""
        by_topic: dict[str, list[QuizQuestion]] = {}
        for question in pool:
            by_topic.setdefault(question.topic_id, []).append(question)

        order = list(by_topic)
        rng.shuffle(order)
        selected: list[QuizQuestion] = []
        while len(selected) < count:
            progressed = False
            for topic_id in order:
                bucket = by_topic.get(topic_id)
                if bucket:
                    selected.append(bucket.pop())
                    progressed = True
                    if len(selected) >= count:
                        break
            if not progressed:
                break
        return selected

    async def _generate(
        self,
        topic_ids: list[str],
        count: int,
        posting: JobPosting | None,
        difficulty: str | None,
    ) -> list[QuizQuestion]:
        block = self.kb.catalog_for_prompt(topic_ids, max_items=12)
        context = "colloquio tecnico per sviluppatore software"
        if posting:
            context = (
                f"{posting.role_title or 'sviluppatore'} "
                f"({posting.seniority}) presso {posting.company_name or 'azienda non nota'}, "
                f"stack: {', '.join(posting.tech_stack[:8]) or 'non specificato'}"
            )
        try:
            data = await self.ai.complete_json(
                prompts.QUIZ_SYSTEM,
                prompts.quiz_user(block, count, context, difficulty),
                schema=prompts.QUIZ_SCHEMA,
                schema_name="quiz",
                temperature=0.7,
            )
        except Exception as exc:
            logger.warning("Generazione AI delle domande fallita: %s", exc)
            return []

        out: list[QuizQuestion] = []
        for row in data.get("questions") or []:
            question = self._parse_generated(row, topic_ids)
            if question:
                out.append(question)
        return out[:count]

    def _parse_generated(self, row: object, topic_ids: list[str]) -> QuizQuestion | None:
        if not isinstance(row, dict):
            return None
        options = row.get("options")
        if not isinstance(options, list) or len(options) != 4:
            return None
        try:
            answer_index = int(row.get("answer_index", -1))
        except (TypeError, ValueError):
            return None
        if not 0 <= answer_index < 4:
            return None
        topic_id = str(row.get("topic_id", ""))
        if topic_id not in self.kb.topics:
            topic_id = topic_ids[0]
        difficulty = str(row.get("difficulty", "medium"))
        return QuizQuestion(
            id=new_id("gq"),
            topic_id=topic_id,
            prompt=str(row.get("prompt", ""))[:1000],
            options=[str(o)[:500] for o in options],
            answer_index=answer_index,
            explanation=str(row.get("explanation", ""))[:1500],
            difficulty=difficulty if difficulty in {"easy", "medium", "hard"} else "medium",  # type: ignore[arg-type]
            generated=True,
        )

    # --- correzione ---------------------------------------------------------

    @staticmethod
    def grade(quiz: Quiz, submission: QuizSubmission) -> Quiz:
        answers = {a.question_id: a.selected_index for a in submission.answers}
        graded: list[GradedAnswer] = []
        wrong_by_topic: dict[str, int] = {}

        for question in quiz.questions:
            # Domanda saltata: -1 non corrisponde a nessuna opzione, quindi conta come errore.
            selected = answers.get(question.id, -1)
            correct = selected == question.answer_index
            if not correct:
                wrong_by_topic[question.topic_id] = wrong_by_topic.get(question.topic_id, 0) + 1
            graded.append(
                GradedAnswer(
                    question_id=question.id,
                    prompt=question.prompt,
                    selected_index=selected,
                    answer_index=question.answer_index,
                    correct=correct,
                    explanation=question.explanation,
                    topic_id=question.topic_id,
                )
            )

        quiz.graded = graded
        quiz.submitted_at = utcnow()
        quiz.score = (
            round(sum(1 for g in graded if g.correct) / len(graded) * 100) if graded else 0
        )
        quiz.weak_topics = [
            topic_id
            for topic_id, _ in sorted(wrong_by_topic.items(), key=lambda kv: -kv[1])
        ][:5]
        return quiz
