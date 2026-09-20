"""La knowledge base deve caricarsi integra: è il dato su cui si regge tutto."""

from __future__ import annotations

from app.services.knowledge import normalize, tokenize


def test_carica_argomenti_domande_e_problemi(kb):
    assert len(kb.topics) >= 60
    assert len(kb.questions) >= 100
    assert len(kb.problems) >= 10


def test_i_quaranta_concetti_backend_sono_presenti(kb):
    """Le cinque categorie della checklist di riferimento, con i conteggi attesi."""
    attesi = {
        "core-concepts": 10,
        "databases": 10,
        "caching": 5,
        "distributed": 5,
        "reliability": 10,
    }
    for categoria, quanti in attesi.items():
        trovati = [t for t in kb.topics.values() if t.category == categoria]
        assert len(trovati) == quanti, f"{categoria}: attesi {quanti}, trovati {len(trovati)}"


def test_ogni_argomento_ha_contenuto_utile(kb):
    for topic in kb.topics.values():
        assert topic.summary.strip(), f"{topic.id} senza summary"
        assert topic.interview_answer.strip(), f"{topic.id} senza risposta da colloquio"
        assert topic.key_points, f"{topic.id} senza key_points"
        assert topic.estimated_minutes > 0


def test_le_domande_puntano_ad_argomenti_esistenti(kb):
    for question in kb.questions.values():
        assert question.topic_id in kb.topics
        assert len(question.options) == 4
        assert 0 <= question.answer_index < 4
        assert question.explanation.strip()


def test_la_vista_pubblica_della_domanda_non_espone_la_soluzione(kb):
    question = next(iter(kb.questions.values()))
    public = question.public().model_dump()
    assert "answer_index" not in public
    assert "explanation" not in public


def test_normalizzazione_e_tokenizzazione():
    assert normalize("Scalabilità") == "scalabilita"
    tokens = tokenize("Esperienza con Kafka e PostgreSQL")
    assert "kafka" in tokens and "postgresql" in tokens
    assert "con" not in tokens  # stopword


def test_scoring_collega_lo_stack_agli_argomenti_giusti(kb):
    scores = kb.score_topics(["Kafka", "Redis"])
    ranked = [tid for tid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
    assert "dist-30-message-queues" in ranked[:5]
    assert any(tid.startswith("cache-") for tid in ranked[:6])


def test_scoring_ignora_termini_senza_senso(kb):
    assert kb.score_topics(["zzzz", "qwertyuiop"]) == {}


def test_catalogo_per_il_prompt_e_compatto(kb):
    catalog = kb.catalog_for_prompt(["core-01-what-is-an-api", "db-12-indexes"])
    assert "core-01-what-is-an-api" in catalog
    assert len(catalog.splitlines()) == 2
