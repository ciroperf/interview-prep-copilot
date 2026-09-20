"""Generazione e correzione dei quiz."""

from __future__ import annotations

import random

from app.domain.models import QuizAnswer, QuizCreate, QuizSubmission
from app.services.quiz import QuizService


async def test_costruisce_un_quiz_del_numero_richiesto(kb, offline_ai):
    service = QuizService(kb, offline_ai)
    quiz = await service.build(
        QuizCreate(num_questions=8, use_ai=False), rng=random.Random(0)
    )
    assert len(quiz.questions) == 8
    assert len({q.id for q in quiz.questions}) == 8


async def test_distribuisce_le_domande_fra_argomenti_diversi(kb, offline_ai):
    service = QuizService(kb, offline_ai)
    quiz = await service.build(
        QuizCreate(
            topic_ids=["core-04-http-status-codes", "db-12-indexes", "cache-22-eviction"],
            num_questions=6,
            use_ai=False,
        ),
        rng=random.Random(1),
    )
    topics = {q.topic_id for q in quiz.questions}
    assert len(topics) >= 2, "un solo argomento ha monopolizzato il quiz"


async def test_filtra_per_difficolta(kb, offline_ai):
    service = QuizService(kb, offline_ai)
    quiz = await service.build(
        QuizCreate(num_questions=5, difficulty="hard", use_ai=False), rng=random.Random(2)
    )
    assert all(q.difficulty == "hard" for q in quiz.questions)


async def test_correzione_calcola_punteggio_e_argomenti_deboli(kb, offline_ai):
    service = QuizService(kb, offline_ai)
    quiz = await service.build(
        QuizCreate(num_questions=4, use_ai=False), rng=random.Random(3)
    )
    # Prima giusta, le altre sbagliate.
    prima = quiz.questions[0]
    answers = [QuizAnswer(question_id=prima.id, selected_index=prima.answer_index)]
    for question in quiz.questions[1:]:
        answers.append(
            QuizAnswer(
                question_id=question.id,
                selected_index=(question.answer_index + 1) % 4,
            )
        )
    graded = QuizService.grade(quiz, QuizSubmission(answers=answers))

    assert graded.score == 25
    assert graded.submitted_at is not None
    assert sum(1 for g in graded.graded if g.correct) == 1
    assert graded.weak_topics


def test_domanda_non_risposta_conta_come_errore(kb, offline_ai):
    from app.domain.models import Quiz

    question = next(iter(kb.questions.values()))
    quiz = Quiz(questions=[question])
    graded = QuizService.grade(quiz, QuizSubmission(answers=[]))
    assert graded.score == 0
    assert graded.graded[0].selected_index == -1
    assert graded.graded[0].correct is False


async def test_le_opzioni_vengono_mescolate(kb, offline_ai):
    """Nella knowledge base la risposta giusta sta quasi sempre nella stessa
    posizione: il servizio deve mescolare, altrimenti il quiz è aggirabile."""
    from collections import Counter

    service = QuizService(kb, offline_ai)
    quiz = await service.build(
        QuizCreate(num_questions=40, use_ai=False), rng=random.Random(42)
    )
    distribuzione = Counter(q.answer_index for q in quiz.questions)
    assert len(distribuzione) == 4, "tutte e quattro le posizioni devono essere usate"
    assert max(distribuzione.values()) / len(quiz.questions) < 0.5


async def test_il_mescolamento_preserva_la_risposta_corretta(kb, offline_ai):
    service = QuizService(kb, offline_ai)
    quiz = await service.build(
        QuizCreate(num_questions=25, use_ai=False), rng=random.Random(7)
    )
    for shuffled in quiz.questions:
        originale = kb.questions[shuffled.id]
        assert set(shuffled.options) == set(originale.options)
        assert shuffled.options[shuffled.answer_index] == (
            originale.options[originale.answer_index]
        )
