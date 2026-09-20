"""Estrazione del testo dal CV e analisi delle parole chiave."""

from __future__ import annotations

import pytest
from conftest import SAMPLE_JOB

from app.services.cv import CvExtractionError, CvService, extract_text, keyword_gap
from app.services.jobs import JobAnalyzer

CV = """
Mario Rossi - Backend Developer

Esperienza
- Sviluppato microservizi in Python con FastAPI per la piattaforma pagamenti
- Ottimizzato query PostgreSQL riducendo la latenza p99 del 40%
- Gestito deploy su Docker in ambiente di produzione
- Partecipazione alle riunioni di team

Competenze
Python, PostgreSQL, Docker, Git
"""


def test_estrae_testo_da_txt():
    assert "Mario Rossi" in extract_text("cv.txt", CV.encode("utf-8"))


def test_estrae_testo_da_markdown():
    assert "Mario Rossi" in extract_text("cv.md", CV.encode("utf-8"))


def test_rifiuta_formati_non_supportati():
    with pytest.raises(CvExtractionError, match="Formato non supportato"):
        extract_text("cv.pages", b"contenuto")


def test_gestisce_encoding_non_utf8():
    testo = extract_text("cv.txt", "Curriculum di José".encode("latin-1"))
    assert "Curriculum" in testo


def test_keyword_gap_separa_presenti_e_assenti():
    posting = JobAnalyzer.heuristic_analysis(SAMPLE_JOB)
    matched, missing = keyword_gap(CV, posting)
    assert "Python" in matched
    assert "PostgreSQL" in matched
    assert "Kafka" in missing, "Kafka non è nel CV e deve risultare mancante"
    assert "Kubernetes" in missing


async def test_revisione_euristica_senza_ai(offline_ai):
    posting = JobAnalyzer.heuristic_analysis(SAMPLE_JOB)
    review = await CvService(offline_ai).review(CV, posting, filename="cv.txt")

    assert review.ai_generated is False
    assert 0 <= review.overall_score <= 100
    assert review.matched_keywords and review.missing_keywords
    assert review.suggestions
    assert any("Kafka" in w for w in review.weaknesses)


async def test_revisione_segnala_le_voci_senza_risultato(offline_ai):
    posting = JobAnalyzer.heuristic_analysis(SAMPLE_JOB)
    review = await CvService(offline_ai).review(CV, posting)
    originali = {r.original for r in review.bullet_rewrites}
    assert any("riunioni di team" in o for o in originali)


async def test_revisione_funziona_anche_senza_annuncio(offline_ai):
    review = await CvService(offline_ai).review(CV, None)
    assert review.job_id == ""
    assert review.summary
