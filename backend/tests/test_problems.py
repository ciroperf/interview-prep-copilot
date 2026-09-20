"""Le soluzioni di riferimento devono superare i test che accompagnano i problemi."""

from __future__ import annotations

import pytest

from app.services.knowledge import get_knowledge_base

PROBLEMI = list(get_knowledge_base().problems.values())


@pytest.mark.parametrize("problem", PROBLEMI, ids=lambda p: p.id)
def test_la_soluzione_di_riferimento_passa_tutti_i_test(problem):
    namespace: dict = {}
    exec(problem.solution, namespace)  # noqa: S102 - contenuto nostro, versionato nel repo
    func = namespace[problem.function_name]
    for index, case in enumerate(problem.tests):
        assert func(**case.kwargs) == case.expected, f"{problem.id} caso #{index}"


@pytest.mark.parametrize("problem", PROBLEMI, ids=lambda p: p.id)
def test_ogni_problema_e_completo(problem):
    assert problem.statement.strip()
    assert problem.function_name in problem.starter_code
    assert len(problem.tests) >= 3
    assert problem.hints, "senza hint il problema non è utilizzabile per lo studio"


def test_la_vista_pubblica_nasconde_soluzione_e_test_nascosti():
    problem = next(p for p in PROBLEMI if any(t.hidden for t in p.tests))
    public = problem.public()
    assert "solution" not in public
    assert all(not t["hidden"] for t in public["tests"])
    assert len(public["tests"]) < len(problem.tests)
