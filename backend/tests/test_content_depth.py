"""Soglie di profondità sui contenuti del repository.

La knowledge base è il prodotto: una scheda che si ferma alla definizione non
serve a preparare un colloquio. Queste soglie sono il minimo sotto cui un
argomento non va pubblicato, e valgono solo per i contenuti versionati - non
per quelli generati dall'AI a partire da un annuncio, che nascono più magri
per costruzione.
"""

from __future__ import annotations

import pytest

MIN_DEEP_DIVE = 900
MIN_KEY_POINTS = 6
MIN_FOLLOW_UPS = 3


def _del_repository(kb):
    """Solo i contenuti versionati: i custom arrivano dall'AI e hanno altre regole."""
    return [t for t in kb.topics.values() if not t.custom]


def test_ogni_argomento_ha_una_spiegazione_lunga(kb):
    corti = [
        f"{t.id} ({len(t.deep_dive)})"
        for t in _del_repository(kb)
        if len(t.deep_dive) < MIN_DEEP_DIVE
    ]
    assert not corti, f"deep_dive sotto {MIN_DEEP_DIVE} caratteri: {corti}"


def test_ogni_argomento_ha_abbastanza_punti_chiave(kb):
    scarsi = [
        f"{t.id} ({len(t.key_points)})"
        for t in _del_repository(kb)
        if len(t.key_points) < MIN_KEY_POINTS
    ]
    assert not scarsi, f"meno di {MIN_KEY_POINTS} punti chiave: {scarsi}"


def test_ogni_argomento_ha_esempi_e_segnali_senior(kb):
    """Le due sezioni che distinguono il ripasso dallo studio."""
    senza_esempi = [t.id for t in _del_repository(kb) if not t.examples]
    senza_segnali = [t.id for t in _del_repository(kb) if not t.senior_signals]
    assert not senza_esempi, f"argomenti senza esempi: {senza_esempi}"
    assert not senza_segnali, f"argomenti senza senior_signals: {senza_segnali}"


def test_le_domande_di_approfondimento_hanno_una_risposta(kb):
    """Una domanda senza risposta lascia il lavoro a metà."""
    problemi = []
    for topic in _del_repository(kb):
        if len(topic.follow_ups) < MIN_FOLLOW_UPS:
            problemi.append(f"{topic.id}: solo {len(topic.follow_ups)} follow_up")
        for follow_up in topic.follow_ups:
            if not follow_up.answer.strip():
                problemi.append(f"{topic.id}: '{follow_up.question[:40]}' senza risposta")
    assert not problemi, problemi


def test_ogni_argomento_ha_la_risposta_da_dare_a_voce(kb):
    """interview_answer è la sezione con cui l'utente si presenta al colloquio."""
    mancanti = [t.id for t in _del_repository(kb) if len(t.interview_answer) < 200]
    assert not mancanti, f"interview_answer troppo corta o assente: {mancanti}"


@pytest.mark.parametrize("campo", ["trade_offs", "pitfalls", "related"])
def test_le_sezioni_di_contesto_sono_compilate(kb, campo):
    vuoti = [t.id for t in _del_repository(kb) if not getattr(t, campo)]
    assert not vuoti, f"{campo} vuoto in: {vuoti}"


def test_gli_argomenti_collegati_esistono(kb):
    """Un related che punta nel vuoto è un vicolo cieco nella navigazione."""
    rotti = [
        f"{t.id} -> {altro}"
        for t in kb.topics.values()
        for altro in t.related
        if altro not in kb.topics
    ]
    assert not rotti, f"collegamenti a argomenti inesistenti: {rotti}"


def test_le_risorse_hanno_un_titolo_e_un_url_sensato(kb):
    problemi = [
        f"{t.id}: {r.title or '(senza titolo)'}"
        for t in _del_repository(kb)
        for r in t.resources
        if not r.title or (r.url and not r.url.startswith("https://"))
    ]
    assert not problemi, problemi
