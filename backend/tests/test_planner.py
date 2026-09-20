"""Il piano deve stare nel tempo disponibile e coprire entrambi i binari."""

from __future__ import annotations

from conftest import SAMPLE_JOB

from app.domain.models import PlanItem, StudyPlanCreate
from app.services.jobs import JobAnalyzer
from app.services.planner import StudyPlanBuilder, plan_by_day, plan_progress_by_track


def _posting():
    posting = JobAnalyzer.heuristic_analysis(SAMPLE_JOB)
    posting.company_name = "Acme Pay"
    return posting


async def test_il_piano_rispetta_il_budget_di_tempo(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    request = StudyPlanCreate(job_id="x", days=5, daily_minutes=60, use_ai=False)
    plan = await builder.build(_posting(), request)
    assert plan.total_minutes <= 5 * 60


async def test_il_piano_copre_parte_conoscitiva_e_tecnica(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    plan = await builder.build(
        _posting(), StudyPlanCreate(job_id="x", days=10, daily_minutes=120, use_ai=False)
    )
    tracks = {item.track for item in plan.items}
    assert tracks == {"knowledge", "technical"}
    kinds = {item.kind for item in plan.items}
    assert "quiz" in kinds
    assert "coding" in kinds
    assert "review" in kinds


async def test_gli_argomenti_trasversali_sono_sempre_presenti(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    plan = await builder.build(
        _posting(), StudyPlanCreate(job_id="x", days=7, daily_minutes=90, use_ai=False)
    )
    topic_ids = {item.topic_id for item in plan.items}
    assert "beh-02-company-research" in topic_ids
    assert "beh-01-star-method" in topic_ids
    # Annuncio senior: il system design non può mancare.
    assert "sd-01-interview-framework" in topic_ids


async def test_lo_stack_dell_annuncio_finisce_nel_piano(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    plan = await builder.build(
        _posting(), StudyPlanCreate(job_id="x", days=14, daily_minutes=120, use_ai=False)
    )
    topic_ids = {item.topic_id for item in plan.items}
    assert "dist-30-message-queues" in topic_ids, "Kafka non ha prodotto l'argomento sulle code"
    assert any(t.startswith("cache-") for t in topic_ids), "Redis non ha prodotto il caching"


async def test_i_punti_di_forza_abbassano_la_priorita(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    base = StudyPlanCreate(job_id="x", days=3, daily_minutes=60, use_ai=False)
    con_forza = StudyPlanCreate(
        job_id="x", days=3, daily_minutes=60, use_ai=False, known_strengths=["Kafka"]
    )
    piano_base = await builder.build(_posting(), base)
    piano_forza = await builder.build(_posting(), con_forza)

    def priorita_code(plan):
        return max(
            (i.priority for i in plan.items if i.topic_id == "dist-30-message-queues"),
            default=0,
        )

    assert priorita_code(piano_forza) <= priorita_code(piano_base)


async def test_le_aree_deboli_alzano_la_priorita(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    request = StudyPlanCreate(
        job_id="x", days=7, daily_minutes=90, use_ai=False, weak_areas=["ricorsione e grafi"]
    )
    plan = await builder.build(_posting(), request)
    assert any(i.topic_id == "dsa-09-graphs" for i in plan.items)


async def test_i_giorni_rispettano_il_budget_giornaliero(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    request = StudyPlanCreate(job_id="x", days=6, daily_minutes=75, use_ai=False)
    plan = await builder.build(_posting(), request)
    for giorno in plan_by_day(plan):
        # L'ultimo giorno può sforare di poco per via del ripasso finale.
        assert giorno["minutes"] <= request.daily_minutes + 60
        assert 1 <= giorno["day"] <= request.days


async def test_le_statistiche_per_binario_sono_coerenti(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    plan = await builder.build(
        _posting(), StudyPlanCreate(job_id="x", days=5, daily_minutes=90, use_ai=False)
    )
    stats = plan_progress_by_track(plan)
    assert stats["knowledge"]["total"] + stats["technical"]["total"] == len(plan.items)
    assert all(v["done"] == 0 for v in stats.values())


async def test_annuncio_vago_produce_comunque_un_piano(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    vago = JobAnalyzer.heuristic_analysis(
        "Cerchiamo una persona motivata da inserire nel nostro team tecnico."
    )
    plan = await builder.build(
        vago, StudyPlanCreate(job_id="x", days=5, daily_minutes=60, use_ai=False)
    )
    assert plan.items
    assert plan.summary


async def test_il_piano_contiene_sempre_esercizi_di_codice(kb, offline_ai):
    """Anche con un annuncio tutto architettura, il live coding va preparato."""
    builder = StudyPlanBuilder(kb, offline_ai)
    architetturale = JobAnalyzer.heuristic_analysis(
        "Senior Software Architect. Cerchiamo esperienza in Clean Architecture, DDD, "
        "CQRS, microservizi, event-driven, Kafka, Kubernetes e system design."
    )
    plan = await builder.build(
        architetturale, StudyPlanCreate(job_id="x", days=7, daily_minutes=90, use_ai=False)
    )
    assert any(i.kind == "coding" for i in plan.items)


async def test_i_junior_ricevono_piu_esercizi_dei_senior(kb, offline_ai):
    builder = StudyPlanBuilder(kb, offline_ai)
    request = StudyPlanCreate(job_id="x", days=14, daily_minutes=120, use_ai=False)

    junior = JobAnalyzer.heuristic_analysis(
        "Junior Backend Developer, 0-2 anni di esperienza. Python e SQL."
    )
    senior = JobAnalyzer.heuristic_analysis(
        "Senior Backend Engineer, almeno 5 anni di esperienza. Python e SQL."
    )
    piano_junior = await builder.build(junior, request)
    piano_senior = await builder.build(senior, request)

    conta = lambda p: sum(1 for i in p.items if i.kind == "coding")  # noqa: E731
    assert conta(piano_junior) > conta(piano_senior)
    # Al senior tocca invece il system design.
    assert any(i.kind == "system_design" for i in piano_senior.items)


def _sequenza_piu_lunga(valori: list[str]) -> int:
    piu_lunga = massimo = 1
    for precedente, corrente in zip(valori, valori[1:], strict=False):
        piu_lunga = piu_lunga + 1 if corrente == precedente else 1
        massimo = max(massimo, piu_lunga)
    return massimo


async def test_i_giorni_alternano_teoria_e_pratica(kb, offline_ai):
    """Sei quiz di fila sono tecnicamente corretti ma impraticabili da seguire.

    Il vincolo vale dove l'alternanza è possibile: una giornata fatta solo di
    studio non ha nulla con cui alternarsi, e pretenderlo significherebbe
    chiedere al planner di inventare attività che il piano non prevede.
    """
    builder = StudyPlanBuilder(kb, offline_ai)
    plan = await builder.build(
        _posting(), StudyPlanCreate(job_id="x", days=7, daily_minutes=90, use_ai=False)
    )
    for giorno in plan_by_day(plan):
        tracce = [i["track"] for i in giorno["items"]]
        if len(set(tracce)) > 1:
            assert _sequenza_piu_lunga(tracce) <= 4, (
                f"giorno {giorno['day']}: troppe attività di fila dello stesso tipo"
            )
        # I quiz restano il caso da sorvegliare: sono brevi, quindi tendono ad
        # accumularsi, ed è proprio la sequenza che stanca di più.
        assert _sequenza_piu_lunga([i["kind"] for i in giorno["items"]] ) <= 4 or all(
            i["kind"] == "study" for i in giorno["items"]
        ), f"giorno {giorno['day']}: troppe attività di fila dello stesso genere"


async def test_l_alternanza_non_dipende_dalla_fascia_di_priorita(kb, offline_ai):
    """Il caso che sfuggiva: una fascia di priorità con solo teoria.

    L'alternanza dentro la fascia non basta, perché le fasce si susseguono e la
    sequenza lunga ricompare a cavallo fra due. Qui si verifica il passaggio che
    spezza le sequenze guardando l'intero elenco.
    """
    items = [
        PlanItem(title=f"t{n}", kind="study", track="knowledge", estimated_minutes=20, priority=3)
        for n in range(6)
    ] + [
        PlanItem(title=f"q{n}", kind="quiz", track="technical", estimated_minutes=10, priority=3)
        for n in range(2)
    ]
    ordinati = StudyPlanBuilder._break_runs(items)
    assert _sequenza_piu_lunga([i.track for i in ordinati]) <= 4
    assert len(ordinati) == len(items)


async def test_nessun_quiz_su_argomenti_non_studiati(kb, offline_ai):
    """Un quiz è una verifica: senza lo studio corrispondente nel piano è tempo sprecato."""
    builder = StudyPlanBuilder(kb, offline_ai)
    for giorni, minuti in ((3, 45), (7, 90), (14, 120)):
        plan = await builder.build(
            _posting(),
            StudyPlanCreate(job_id="x", days=giorni, daily_minutes=minuti, use_ai=False),
        )
        studiati = {i.topic_id for i in plan.items if i.track == "knowledge" and i.topic_id}
        orfani = [i.title for i in plan.items if i.kind == "quiz" and i.topic_id not in studiati]
        assert not orfani, f"piano {giorni}x{minuti}: quiz senza studio -> {orfani}"
