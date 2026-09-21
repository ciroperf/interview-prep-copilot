"""Ampliamento della knowledge base a partire dagli annunci."""

from __future__ import annotations

import pytest
import yaml
from conftest import SAMPLE_JOB

from app.domain.models import StudyPlanCreate, TopicCreate, TopicDraft
from app.services.curator import KnowledgeCurator
from app.services.jobs import JobAnalyzer
from app.services.knowledge import KnowledgeBase
from app.services.planner import StudyPlanBuilder
from app.storage.jsonfiles import JsonFileRepository

DRAFT = TopicDraft(
    title="Kubernetes per il colloquio",
    summary=(
        "Kubernetes orchestra container: dichiari lo stato desiderato e il control "
        "plane lavora per farlo combaciare con quello reale."
    ),
    category="engineering",
    tags=["kubernetes", "k8s", "container"],
    key_points=["Pod, Deployment, Service", "Liveness e readiness probe"],
    interview_answer="Descrivo Kubernetes come un loop di riconciliazione continuo.",
)


@pytest.fixture
def curator(kb: KnowledgeBase, offline_ai, data_dir):
    return KnowledgeCurator(kb, offline_ai, JsonFileRepository(data_dir))


def _posting():
    return JobAnalyzer.heuristic_analysis(SAMPLE_JOB)


def test_rileva_le_lacune_dell_annuncio(curator):
    gaps = curator.find_gaps(_posting())
    per_termine = {g.term: g for g in gaps}

    assert per_termine["Kubernetes"].covered is False, "Kubernetes non ha un argomento dedicato"
    assert per_termine["Kafka"].covered is True, "Kafka ha già il suo argomento"


def test_le_lacune_indicano_l_argomento_piu_vicino(curator):
    gaps = {g.term: g for g in curator.find_gaps(_posting())}
    kubernetes = gaps["Kubernetes"]
    assert kubernetes.best_topic_title, "va mostrato l'argomento correlato più vicino"
    assert kubernetes.coverage_score > 0


def test_le_lacune_sono_ordinate_per_importanza(curator):
    gaps = curator.find_gaps(_posting())
    mancanti = [g for g in gaps if not g.covered]
    assert mancanti, "l'annuncio di esempio ha lacune"
    assert mancanti == sorted(mancanti, key=lambda g: -g.importance)
    # Le lacune vengono prima di ciò che è già coperto.
    assert gaps.index(mancanti[0]) == 0


def test_i_termini_generici_non_diventano_lacune(curator):
    posting = JobAnalyzer.heuristic_analysis(
        "Cerchiamo sviluppatore con metodologia Agile, Scrum e buona conoscenza di Git."
    )
    assert [g.term for g in curator.find_gaps(posting)] == []


async def test_aggiunge_un_argomento_da_contenuto_manuale(curator, kb):
    prima = len(kb.topics)
    topic, questions = await curator.create_topic(
        TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0)
    )

    assert topic.custom is True
    assert topic.source_term == "Kubernetes"
    assert topic.created_at is not None
    assert questions == []
    assert len(kb.topics) == prima + 1
    assert kb.topics[topic.id].title == "Kubernetes per il colloquio"


async def test_l_argomento_aggiunto_diventa_il_match_migliore(curator, kb):
    _score_prima, id_prima, dedicato_prima = kb.coverage("Kubernetes")
    assert dedicato_prima is False

    topic, _ = await curator.create_topic(
        TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0)
    )

    _score, id_dopo, dedicato_dopo = kb.coverage("Kubernetes")
    assert id_dopo == topic.id != id_prima
    assert dedicato_dopo is True


async def test_l_argomento_aggiunto_entra_nel_piano(curator, kb, offline_ai):
    await curator.create_topic(TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0))

    builder = StudyPlanBuilder(kb, offline_ai)
    plan = await builder.build(
        _posting(), StudyPlanCreate(job_id="x", days=10, daily_minutes=120, use_ai=False)
    )
    assert any(i.topic_id.startswith("custom-kubernetes") for i in plan.items)


async def test_senza_ai_e_senza_contenuto_si_rifiuta(curator):
    with pytest.raises(ValueError, match="modello AI"):
        await curator.create_topic(TopicCreate(term="Kubernetes"))


async def test_l_argomento_sopravvive_al_riavvio(curator, kb, offline_ai, data_dir):
    topic, _ = await curator.create_topic(
        TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0)
    )

    # Nuova istanza, come dopo il restart di un container.
    kb_nuova = KnowledgeBase()
    assert topic.id not in kb_nuova.topics
    KnowledgeCurator(kb_nuova, offline_ai, JsonFileRepository(data_dir)).load_persisted()
    assert topic.id in kb_nuova.topics


async def test_id_univoco_su_termini_ripetuti(curator):
    primo, _ = await curator.create_topic(
        TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0)
    )
    secondo, _ = await curator.create_topic(
        TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0)
    )
    assert primo.id != secondo.id


async def test_elimina_solo_gli_argomenti_aggiunti(curator, kb):
    topic, _ = await curator.create_topic(
        TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0)
    )
    assert curator.delete_topic(topic.id) is True
    assert topic.id not in kb.topics
    assert curator.delete_topic("core-01-what-is-an-api") is False
    assert "core-01-what-is-an-api" in kb.topics


async def test_export_produce_yaml_nel_formato_dei_contenuti(curator):
    await curator.create_topic(TopicCreate(term="Kubernetes", draft=DRAFT, num_questions=0))
    export = curator.export()

    assert export["count"] == 1
    righe = yaml.safe_load(export["topics_yaml"])
    assert isinstance(righe, list) and len(righe) == 1
    riga = righe[0]
    # Deve poter essere ricaricato come un normale file di app/content/.
    from app.domain.models import Topic

    ricostruito = Topic(**riga)
    assert ricostruito.title == DRAFT.title
    # I marcatori di runtime non vanno nel file versionato.
    assert "custom" not in riga
    assert "created_at" not in riga


async def test_export_vuoto_resta_valido(curator):
    export = curator.export()
    assert export["count"] == 0
    assert yaml.safe_load(export["topics_yaml"]) is None


class _FakeAI:
    """Finto client AI: restituisce una risposta fissa, senza rete."""

    available = True

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    async def complete_json(self, system: str, user: str, **_kwargs) -> dict:
        self.calls.append((system, user))
        return self.payload


AI_PAYLOAD = {
    "title": "Kubernetes: orchestrazione di container",
    "category": "engineering",
    "track": "knowledge",
    "level": "medium",
    "tags": ["kubernetes", "container", "devops"],
    "summary": "Kubernetes mantiene lo stato reale allineato a quello dichiarato.",
    "key_points": ["Pod e Deployment", "Probe di liveness e readiness"],
    "interview_answer": "Lo descrivo come un loop di riconciliazione.",
    "pitfalls": ["Usarlo per due servizi e cinquanta utenti"],
    "follow_up_questions": ["Differenza fra Deployment e StatefulSet?"],
    "estimated_minutes": 35,
    "questions": [
        {
            "prompt": "Cosa fa il control plane di Kubernetes?",
            "options": [
                "Compila le immagini",
                "Riconcilia stato reale e desiderato",
                "Instrada il DNS",
                "Cifra i volumi",
            ],
            "answer_index": 1,
            "explanation": "È un loop di riconciliazione continuo.",
            "difficulty": "medium",
        },
        {
            "prompt": "Domanda con opzioni malformate",
            "options": ["solo", "due"],
            "answer_index": 0,
            "explanation": "va scartata",
        },
    ],
}


async def test_generazione_con_ai(kb, data_dir):
    ai = _FakeAI(AI_PAYLOAD)
    curator = KnowledgeCurator(kb, ai, JsonFileRepository(data_dir))  # type: ignore[arg-type]

    topic, questions = await curator.create_topic(
        TopicCreate(term="Kubernetes", num_questions=3), _posting()
    )

    assert topic.title == "Kubernetes: orchestrazione di container"
    assert topic.custom is True
    assert topic.estimated_minutes == 35
    # La domanda malformata (due opzioni invece di quattro) va scartata, non accettata.
    assert len(questions) == 1
    assert questions[0].generated is True
    assert kb.questions_by_topic[topic.id] == [questions[0].id]
    # Il contesto dell'annuncio deve arrivare al modello.
    assert "Backend Engineer" in ai.calls[0][1]


async def test_risposta_ai_inutilizzabile_viene_rifiutata(kb, data_dir):
    ai = _FakeAI({"title": "Vuoto"})
    curator = KnowledgeCurator(kb, ai, JsonFileRepository(data_dir))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="contenuto utilizzabile"):
        await curator.create_topic(TopicCreate(term="Kubernetes"))
    assert not kb.custom_topics(), "niente deve essere registrato se la generazione fallisce"


PAYLOAD_RICCO = {
    **AI_PAYLOAD,
    "deep_dive": "Un paragrafo lungo che spiega come funziona davvero.\n\nE un secondo.",
    "examples": [
        {"title": "Un manifest minimo", "language": "yaml", "code": "kind: Deployment\n",
         "note": "Perche' conta"},
        {"title": "Senza codice", "language": "yaml"},
    ],
    "trade_offs": [
        {"option": "Kubernetes", "pros": "Portabile", "cons": "Complesso", "when": "Molti servizi"},
        {"pros": "orfano senza opzione"},
    ],
    "numbers": ["Un pod parte in pochi secondi"],
    "senior_signals": ["Valuta il carico operativo, non le funzionalita'"],
    "follow_ups": [
        {"question": "Deployment o StatefulSet?", "answer": "Il secondo quando l'identita' conta."},
        {"question": "Domanda senza risposta"},
    ],
    "resources": [
        {
            "title": "Documentazione ufficiale",
            "url": "https://kubernetes.io/docs/home/",
            "kind": "doc",
        },
        {"title": "Link non sicuro", "url": "http://esempio.it/inventato"},
        {"title": "Solo titolo, url incerto"},
    ],
}


async def test_la_generazione_riempie_le_sezioni_profonde(kb, data_dir):
    """Le schede generate devono stare nel catalogo, non sembrare un riassunto."""
    curator = KnowledgeCurator(kb, _FakeAI(PAYLOAD_RICCO), JsonFileRepository(data_dir))  # type: ignore[arg-type]

    topic, _ = await curator.create_topic(TopicCreate(term="Kubernetes"))

    assert topic.deep_dive
    assert len(topic.examples) == 1, "l'esempio senza codice va scartato"
    assert topic.examples[0].language == "yaml"
    assert len(topic.trade_offs) == 1, "il trade-off senza opzione va scartato"
    assert topic.numbers and topic.senior_signals
    assert len(topic.follow_ups) == 1, "una domanda senza risposta lascia il lavoro a meta'"
    assert topic.follow_ups[0].answer


async def test_gli_url_non_https_vengono_scartati(kb, data_dir):
    """Un modello che non conosce una fonte tende a inventare un permalink.

    Il titolo resta - la fonte e' comunque cercabile - ma l'URL sospetto no:
    un link rotto fa perdere tempo e toglie credibilita' a tutta la scheda.
    """
    curator = KnowledgeCurator(kb, _FakeAI(PAYLOAD_RICCO), JsonFileRepository(data_dir))  # type: ignore[arg-type]

    topic, _ = await curator.create_topic(TopicCreate(term="Kubernetes"))

    assert len(topic.resources) == 3, "nessuna fonte va persa, solo gli URL sospetti"
    per_titolo = {r.title: r.url for r in topic.resources}
    assert per_titolo["Documentazione ufficiale"].startswith("https://")
    assert per_titolo["Link non sicuro"] == ""
    assert per_titolo["Solo titolo, url incerto"] == ""


async def test_il_suggerimento_arriva_al_modello(kb, data_dir):
    """L'etichetta breve non basta: il suggerimento dice cosa va coperto."""
    ai = _FakeAI(PAYLOAD_RICCO)
    curator = KnowledgeCurator(kb, ai, JsonFileRepository(data_dir))  # type: ignore[arg-type]

    await curator.create_topic(
        TopicCreate(
            term="Salesforce Commerce Cloud",
            suggestion="Studiare SFCC: template/stencil, controllers, hooks e integrazioni.",
        )
    )

    prompt = ai.calls[0][1]
    assert "template/stencil" in prompt
    assert "hooks" in prompt


@pytest.mark.parametrize(
    ("suggerimento", "atteso"),
    [
        ("Studiare Salesforce Commerce Cloud (SFCC) specific: template e hooks.",
         "Salesforce Commerce Cloud"),
        ("Approfondire integrazioni pagamenti pratiche: flow 3DS, webhook, PCI.",
         "integrazioni pagamenti pratiche"),
        ("Pratica su end-to-end testing per eCommerce (Cypress/Playwright).",
         "end-to-end testing per eCommerce"),
        ("Non coperto dal catalogo: Osservability e monitoring, caching.",
         "Osservability"),
    ],
)
def test_l_etichetta_si_ricava_dalla_frase_del_suggerimento(suggerimento, atteso):
    """Da quella etichetta nasce l'id, quindi deve essere corta e stabile."""
    assert KnowledgeCurator.term_from_suggestion(suggerimento) == atteso
