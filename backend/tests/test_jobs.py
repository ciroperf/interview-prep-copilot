"""L'analisi euristica deve reggere da sola, senza AI configurata."""

from __future__ import annotations

import pytest
from conftest import SAMPLE_JOB

from app.services.jobs import JobAnalyzer


def test_estrae_lo_stack_tecnologico():
    posting = JobAnalyzer.heuristic_analysis(SAMPLE_JOB)
    for atteso in ["Python", "PostgreSQL", "Kafka", "Docker", "Kubernetes", "Redis"]:
        assert atteso in posting.tech_stack, f"{atteso} non riconosciuto"


def test_riconosce_seniority_luogo_e_modalita():
    posting = JobAnalyzer.heuristic_analysis(SAMPLE_JOB)
    assert posting.seniority == "senior"
    assert posting.location == "Milano"
    assert posting.work_mode == "ibrido"


def test_estrae_titolo_e_responsabilita():
    posting = JobAnalyzer.heuristic_analysis(SAMPLE_JOB)
    assert "Backend Engineer" in posting.role_title
    assert any("microservizi" in r.lower() for r in posting.responsibilities)


def test_le_tecnologie_ripetute_pesano_di_piu():
    testo = "Cerchiamo uno sviluppatore Python. Python è il nostro linguaggio principale. "
    testo += "Usiamo Python ovunque. Conoscenza base di Java gradita."
    posting = JobAnalyzer.heuristic_analysis(testo)
    per_nome = {r.name: r.importance for r in posting.requirements}
    assert per_nome["Python"] > per_nome["Java"]


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("Stage curricolare per sviluppatore", "intern"),
        ("Junior Developer, 0-2 anni di esperienza", "junior"),
        ("Cerchiamo un Tech Lead per il team", "staff"),
        ("Sviluppatore con 3-5 anni di esperienza", "mid"),
        ("Sviluppatore software", "unknown"),
    ],
)
def test_pattern_di_seniority(testo, atteso):
    assert JobAnalyzer.heuristic_analysis(testo).seniority == atteso


async def test_analyze_senza_ai_restituisce_comunque_un_risultato(offline_ai):
    analyzer = JobAnalyzer(offline_ai)
    posting = await analyzer.analyze(SAMPLE_JOB, company_name="Acme Pay")
    assert posting.analyzed_with_ai is False
    assert posting.company_name == "Acme Pay"
    assert posting.tech_stack


async def test_scheda_azienda_senza_ai_spiega_cosa_fare_a_mano(offline_ai):
    analyzer = JobAnalyzer(offline_ai)
    posting = await analyzer.analyze(SAMPLE_JOB)
    profile = await analyzer.research_company(posting)
    assert profile.ai_generated is False
    assert profile.questions_to_ask
    assert "AI non configurata" in profile.research_notes
