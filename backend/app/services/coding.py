"""Selezione dei problemi di coding e revisione delle soluzioni inviate."""

from __future__ import annotations

import logging

from ..ai import prompts
from ..ai.client import AIClient
from ..config import Settings
from ..domain.models import CodeReview, CodingProblem, JobPosting
from . import sandbox
from .knowledge import KnowledgeBase

logger = logging.getLogger(__name__)


class CodingService:
    def __init__(self, kb: KnowledgeBase, ai: AIClient, settings: Settings) -> None:
        self.kb = kb
        self.ai = ai
        self.settings = settings

    def recommend(self, posting: JobPosting | None, limit: int = 6) -> list[CodingProblem]:
        """Problemi più pertinenti all'annuncio, o un mix equilibrato se manca."""
        if posting is None:
            return sorted(
                self.kb.problems.values(), key=lambda p: (p.difficulty != "easy", p.title)
            )[:limit]

        terms = posting.tech_stack + [r.name for r in posting.requirements]
        terms.append(posting.role_title)
        scores = self.kb.score_topics([t for t in terms if t])
        ranked_topics = [tid for tid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]

        picked = self.kb.problems_for(ranked_topics)
        if len(picked) < limit:
            for problem in self.kb.problems.values():
                if problem not in picked:
                    picked.append(problem)
        # I junior partono dai problemi facili, i senior da quelli medi.
        easy_first = posting.seniority in {"intern", "junior", "unknown"}
        order = {"easy": 0, "medium": 1, "hard": 2}
        picked.sort(key=lambda p: order[p.difficulty] if easy_first else -order[p.difficulty])
        return picked[:limit]

    async def review(self, problem: CodingProblem, code: str) -> CodeReview:
        review = CodeReview(problem_id=problem.id, tests_total=len(problem.tests))

        execution_report = ""
        if self.settings.enable_code_execution:
            result = sandbox.run_tests(
                problem,
                code,
                timeout_seconds=self.settings.code_execution_timeout_seconds,
                memory_mb=self.settings.code_execution_memory_mb,
            )
            review.executed = result.executed
            review.outcomes = result.outcomes
            review.tests_passed = result.passed
            execution_report = result.report()
            if result.fatal:
                review.correctness = result.fatal

        if self.ai.available:
            try:
                data = await self.ai.complete_json(
                    prompts.CODE_REVIEW_SYSTEM,
                    prompts.code_review_user(
                        self._problem_text(problem), code, execution_report
                    ),
                    schema=prompts.CODE_REVIEW_SCHEMA,
                    schema_name="revisione_codice",
                    temperature=0.3,
                )
                review.verdict = str(data.get("verdict", ""))[:600]
                review.correctness = str(data.get("correctness", review.correctness))[:1500]
                review.complexity = str(data.get("complexity", ""))[:600]
                review.strengths = [str(s)[:300] for s in (data.get("strengths") or [])][:8]
                review.improvements = [str(s)[:400] for s in (data.get("improvements") or [])][:8]
                review.interview_notes = str(data.get("interview_notes", ""))[:1500]
                review.ai_generated = True
                return review
            except Exception as exc:
                logger.warning("Revisione AI del codice fallita: %s", exc)

        self._fallback_review(review, problem, execution_report)
        return review

    @staticmethod
    def _problem_text(problem: CodingProblem) -> str:
        return (
            f"{problem.title} (difficoltà: {problem.difficulty})\n\n"
            f"{problem.statement}\n\n"
            f"Firma attesa: {problem.function_name}\n"
            f"Complessità obiettivo: {problem.target_complexity or 'non specificata'}"
        )

    @staticmethod
    def _fallback_review(
        review: CodeReview, problem: CodingProblem, execution_report: str
    ) -> None:
        """Senza AI restituiamo comunque l'esito dei test e i riferimenti utili."""
        if review.executed:
            if review.tests_passed == review.tests_total and review.tests_total:
                review.verdict = "Tutti i test superati."
                review.strengths = ["La soluzione supera tutti i casi di prova disponibili."]
            else:
                review.verdict = (
                    f"{review.tests_passed}/{review.tests_total} test superati: "
                    "la soluzione non è ancora corretta."
                )
            review.correctness = review.correctness or execution_report
        else:
            review.verdict = (
                "Esecuzione del codice disabilitata su questa istanza e AI non "
                "configurata: confronta la tua soluzione con i suggerimenti del problema."
            )
        review.complexity = f"Obiettivo dichiarato: {problem.target_complexity or 'non indicato'}"
        review.improvements = list(problem.hints)
