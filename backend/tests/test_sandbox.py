"""Esecuzione dei test sul codice utente (disattivata di default in produzione)."""

from __future__ import annotations

import sys

import pytest

from app.services.knowledge import get_knowledge_base
from app.services.sandbox import run_tests

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="i limiti di risorsa usati dal runner sono specifici di Unix",
)

PROBLEM = get_knowledge_base().problems["p-two-sum"]


def test_soluzione_corretta_passa_tutti_i_test():
    result = run_tests(PROBLEM, PROBLEM.solution, timeout_seconds=5)
    assert result.executed
    assert not result.fatal
    assert result.passed == len(PROBLEM.tests)


def test_soluzione_sbagliata_viene_bocciata():
    code = "def two_sum(nums, target):\n    return [0, 0]\n"
    result = run_tests(PROBLEM, code, timeout_seconds=5)
    assert result.passed < len(PROBLEM.tests)
    assert "FALLITO" in result.report()


def test_errore_di_sintassi_riportato_senza_esplodere():
    result = run_tests(PROBLEM, "def two_sum(nums target):", timeout_seconds=5)
    assert result.fatal
    assert "SyntaxError" in result.fatal


def test_funzione_mancante_riportata():
    result = run_tests(PROBLEM, "x = 1", timeout_seconds=5)
    assert "two_sum" in result.fatal


def test_eccezione_a_runtime_non_blocca_gli_altri_test():
    code = "def two_sum(nums, target):\n    raise RuntimeError('boom')\n"
    result = run_tests(PROBLEM, code, timeout_seconds=5)
    assert len(result.outcomes) == len(PROBLEM.tests)
    assert all("RuntimeError" in o.error for o in result.outcomes)


def test_ciclo_infinito_viene_interrotto():
    code = "def two_sum(nums, target):\n    while True:\n        pass\n"
    result = run_tests(PROBLEM, code, timeout_seconds=2)
    assert result.fatal, "il runner deve fermare un'esecuzione che non termina"
