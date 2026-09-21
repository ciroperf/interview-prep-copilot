"""I percorsi devono restare coerenti con il catalogo che indicizzano.

Un percorso rotto non dà errore a video: mostra semplicemente meno argomenti di
quelli promessi. Meglio che sia un test a dirlo.
"""

from __future__ import annotations

import pytest


def test_ogni_percorso_ha_argomenti_esistenti_e_senza_ripetizioni(kb):
    assert kb.packs, "nessun percorso caricato"
    for pack in kb.packs.values():
        assert pack.topic_ids, f"{pack.id}: percorso senza argomenti"
        assert len(pack.topic_ids) == len(set(pack.topic_ids)), (
            f"{pack.id}: lo stesso argomento compare due volte"
        )
        for topic_id in pack.topic_ids:
            assert topic_id in kb.topics, f"{pack.id}: argomento inesistente {topic_id}"


def test_ogni_argomento_sta_in_almeno_un_percorso(kb):
    """Un argomento fuori da ogni percorso si trova solo cercandolo per nome."""
    coperti = {topic_id for pack in kb.packs.values() for topic_id in pack.topic_ids}
    orfani = sorted(set(kb.topics) - coperti)
    assert not orfani, f"argomenti non raggiungibili da un percorso: {orfani}"


def test_le_fonti_sono_motivate(kb):
    """Una fonte senza il perché è solo un link: il valore del percorso sta lì."""
    for pack in kb.packs.values():
        assert pack.sources, f"{pack.id}: percorso senza fonti"
        for source in pack.sources:
            assert source.title, f"{pack.id}: fonte senza titolo"
            assert len(source.note) >= 80, (
                f"{pack.id} / {source.title}: motivazione troppo corta"
            )
            if source.url:
                assert source.url.startswith("https://"), (
                    f"{pack.id} / {source.title}: URL non https"
                )


def test_i_percorsi_hanno_una_descrizione_utilizzabile(kb):
    for pack in kb.packs.values():
        assert pack.title and pack.subtitle, f"{pack.id}: manca titolo o sottotitolo"
        assert len(pack.summary) >= 300, f"{pack.id}: riassunto troppo corto"
        assert pack.for_whom, f"{pack.id}: manca 'a chi serve'"


@pytest.mark.parametrize("pack_id", ["pack-python", "pack-javascript"])
def test_i_percorsi_sui_linguaggi_partono_dalla_scheda_introduttiva(kb, pack_id):
    """eng-06 ed eng-07 restano nel catalogo come porta d'ingresso al percorso."""
    pack = kb.packs[pack_id]
    primo = kb.topics[pack.topic_ids[0]]
    assert primo.category == "languages"


def test_elenco_e_dettaglio_dei_percorsi(client):
    elenco = client.get("/api/knowledge/packs")
    assert elenco.status_code == 200
    dati = elenco.json()
    assert dati["total"] == len(dati["packs"])
    primo = dati["packs"][0]
    assert primo["estimated_minutes"] > 0
    assert primo["topic_count"] > 0

    dettaglio = client.get(f"/api/knowledge/packs/{primo['id']}")
    assert dettaglio.status_code == 200
    corpo = dettaglio.json()
    # Gli argomenti arrivano nell'ordine dichiarato: il percorso è una sequenza.
    assert [t["id"] for t in corpo["topics"]] == corpo["pack"]["topic_ids"]

    assert client.get("/api/knowledge/packs/pack-inesistente").status_code == 404
