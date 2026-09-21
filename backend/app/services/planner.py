"""Costruzione del piano di studi su misura per un singolo annuncio.

Il piano e' diviso in due binari, come richiesto:
  * knowledge -> parte conoscitiva: teoria da saper raccontare, azienda, comportamentale;
  * technical -> parte tecnica: quiz, problemi DSA, system design.

La selezione degli argomenti parte sempre da un punteggio deterministico calcolato
sulla knowledge base. Se l'AI e' disponibile la usiamo per riordinare e motivare le
scelte, ma il piano esiste comunque anche senza.
"""

from __future__ import annotations

import logging
from datetime import date

from ..ai import prompts
from ..ai.client import AIClient
from ..domain.models import JobPosting, PlanItem, Resource, StudyPlan, StudyPlanCreate
from .knowledge import KnowledgeBase, normalize

logger = logging.getLogger(__name__)

# Quanti argomenti passare al modello: abbastanza per scegliere, non tanti da
# far esplodere il prompt.
CANDIDATE_POOL = 34

# I temi trasversali non dipendono dall'annuncio ma servono sempre.
ANCHOR_BEHAVIORAL = "beh-01-star-method"
ANCHOR_COMPANY = "beh-02-company-research"
ANCHOR_SYSTEM_DESIGN = "sd-01-interview-framework"

# Quanti argomenti DSA mandare a esercizio nel piano, per seniority. Un colloquio
# da sviluppatore contiene quasi sempre un esercizio di codice, che l'annuncio lo
# dica o no; i profili junior ne affrontano più dei senior, dove pesa il design.
# È insieme un minimo garantito e un tetto: oltre la quota gli argomenti DSA
# restano nel piano, ma come ripasso, per lasciare spazio al resto.
DSA_QUOTA: dict[str, int] = {
    "intern": 3,
    "junior": 3,
    "mid": 2,
    "senior": 1,
    "staff": 1,
    "unknown": 2,
}

# Ordine di preferenza quando l'annuncio non dà indicazioni: prima ciò che
# ricorre in più problemi, poi i temi specialistici.
DSA_FALLBACK_ORDER = [
    "dsa-03-hash-maps",
    "dsa-01-complexity",
    "dsa-02-arrays-two-pointers",
    "dsa-12-sliding-window",
    "dsa-05-binary-search",
    "dsa-09-graphs",
    "dsa-11-dynamic-programming",
    "dsa-08-trees",
]

# Dalla categoria dell'argomento al tipo di attività, e da questo all'etichetta.
KIND_BY_CATEGORY = {
    "company": "company",
    "behavioral": "behavioral",
    "system-design": "system_design",
}
TITLE_PREFIX = {
    "study": "Studia",
    "company": "Ricerca",
    "behavioral": "Prepara",
    "system_design": "Esercitati",
}


class StudyPlanBuilder:
    def __init__(self, kb: KnowledgeBase, ai: AIClient) -> None:
        self.kb = kb
        self.ai = ai

    # --- API principale -----------------------------------------------------

    async def build(self, posting: JobPosting, request: StudyPlanCreate) -> StudyPlan:
        scores = self._base_scores(posting, request)
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        candidates = [tid for tid, _ in ranked[:CANDIDATE_POOL]]

        rationales: dict[str, str] = {}
        priorities: dict[str, int] = {}
        summary = ""
        focus_areas: list[str] = []
        gap_analysis: list[str] = []
        ai_used = False

        if request.use_ai and self.ai.available and candidates:
            try:
                data = await self.ai.complete_json(
                    prompts.PLAN_SYSTEM,
                    prompts.plan_user(
                        self._job_summary(posting),
                        # Il catalogo INTERO, non i soli candidati: passandogli solo i
                        # piu' affini, il modello non vedeva git, observability, caching
                        # o Docker su un annuncio frontend e li dichiarava "non coperti
                        # dal catalogo". Sono ~3k token, e la lista dei candidati resta
                        # come suggerimento di priorita'.
                        self.kb.catalog_for_prompt(None, max_items=400),
                        request.days,
                        request.daily_minutes,
                        request.known_strengths,
                        request.weak_areas,
                    ),
                    schema=prompts.PLAN_SCHEMA,
                    schema_name="piano_studi",
                    temperature=0.3,
                )
                summary = str(data.get("summary", ""))[:2000]
                focus_areas = [str(x)[:120] for x in (data.get("focus_areas") or [])][:8]
                gap_analysis = [str(x)[:300] for x in (data.get("gap_analysis") or [])][:8]
                for row in data.get("selected_topics") or []:
                    if not isinstance(row, dict):
                        continue
                    topic_id = str(row.get("topic_id", ""))
                    if topic_id not in self.kb.topics:
                        continue
                    try:
                        priority = max(1, min(5, int(row.get("priority", 3))))
                    except (TypeError, ValueError):
                        priority = 3
                    priorities[topic_id] = priority
                    rationales[topic_id] = str(row.get("rationale", ""))[:300]
                for extra in data.get("extra_recommendations") or []:
                    gap_analysis.append(f"Non coperto dal catalogo: {str(extra)[:200]}")
                ai_used = bool(priorities)
            except Exception as exc:
                logger.warning("Generazione AI del piano fallita, uso solo l'euristica: %s", exc)

        if not priorities:
            # Fallback: priorita' derivate dal punteggio, normalizzate su 1-5.
            top = ranked[:CANDIDATE_POOL]
            best = top[0][1] if top else 1.0
            for topic_id, score in top:
                priorities[topic_id] = self._to_priority(score, best)
            focus_areas = focus_areas or self._heuristic_focus(posting)
            gap_analysis = gap_analysis or self._heuristic_gaps(posting, request)
            summary = summary or self._heuristic_summary(posting, request)

        esercizi_dsa = self._ensure_anchors(priorities, rationales, posting)
        self._ensure_weak_areas(priorities, rationales, request)

        items = self._build_items(priorities, rationales, request, esercizi_dsa)
        items = self._fit_to_budget(items, request)
        self._assign_days(items, request)

        plan = StudyPlan(
            job_id=posting.id,
            title=self._plan_title(posting),
            summary=summary,
            interview_date=request.interview_date,
            days=request.days,
            daily_minutes=request.daily_minutes,
            items=items,
            focus_areas=focus_areas,
            gap_analysis=gap_analysis,
            ai_generated=ai_used,
        )
        return plan

    # --- punteggi -----------------------------------------------------------

    def _base_scores(self, posting: JobPosting, request: StudyPlanCreate) -> dict[str, float]:
        """Pesa i termini dell'annuncio e applica le correzioni dichiarate dall'utente."""
        weighted_terms: list[str] = []
        # L'importanza dichiarata nell'annuncio si traduce in ripetizioni del termine,
        # che è il modo più semplice di pesarlo nello scoring.
        for requirement in posting.requirements:
            weighted_terms.extend([requirement.name] * max(1, requirement.importance - 1))
        weighted_terms.extend(posting.tech_stack)
        weighted_terms.extend(posting.interview_focus)
        weighted_terms.extend(posting.responsibilities)
        if posting.role_title:
            weighted_terms.extend([posting.role_title] * 2)

        scores = self.kb.score_topics(weighted_terms)

        # Senza segnali utili (annuncio molto vago) partiamo dai fondamentali.
        if not scores:
            for topic_id, topic in self.kb.topics.items():
                if topic.category in {"core-concepts", "databases", "dsa"}:
                    scores[topic_id] = 2.0

        seniority_bonus = {
            "intern": {"dsa": 2.5, "core-concepts": 2.0, "languages": 1.5},
            "junior": {"dsa": 2.0, "core-concepts": 2.0, "languages": 1.5},
            "mid": {"databases": 1.5, "caching": 1.0, "dsa": 1.0},
            "senior": {"system-design": 3.0, "distributed": 2.0, "reliability": 2.0},
            "staff": {"system-design": 3.5, "distributed": 2.5, "reliability": 2.5},
            "unknown": {"core-concepts": 1.0, "dsa": 1.0},
        }[posting.seniority]
        for topic_id, topic in self.kb.topics.items():
            bonus = seniority_bonus.get(topic.category)
            if bonus:
                scores[topic_id] = scores.get(topic_id, 0.0) + bonus

        # I punti di forza dichiarati scendono, le aree deboli salgono.
        for strength in request.known_strengths:
            for topic_id, delta in self.kb.score_topics([strength]).items():
                scores[topic_id] = scores.get(topic_id, 0.0) - delta * 0.6
        for weakness in request.weak_areas:
            for topic_id, delta in self.kb.score_topics([weakness]).items():
                scores[topic_id] = scores.get(topic_id, 0.0) + delta * 1.2

        return {tid: score for tid, score in scores.items() if score > 0}

    @staticmethod
    def _to_priority(score: float, best: float) -> int:
        if best <= 0:
            return 3
        ratio = score / best
        if ratio >= 0.75:
            return 5
        if ratio >= 0.5:
            return 4
        if ratio >= 0.3:
            return 3
        if ratio >= 0.15:
            return 2
        return 1

    def _ensure_anchors(
        self, priorities: dict[str, int], rationales: dict[str, str], posting: JobPosting
    ) -> set[str]:
        """Alcuni temi vanno nel piano a prescindere da cosa dice l'annuncio.

        Restituisce gli argomenti DSA che possono diventare esercizi di codice.
        """
        anchors = {
            ANCHOR_COMPANY: (
                5,
                "Ogni colloquio inizia dal perché proprio questa azienda: va preparato.",
            ),
            ANCHOR_BEHAVIORAL: (
                4,
                "Le domande comportamentali arrivano sempre e si preparano in anticipo.",
            ),
        }
        if posting.seniority in {"senior", "staff", "mid"}:
            anchors[ANCHOR_SYSTEM_DESIGN] = (
                5 if posting.seniority in {"senior", "staff"} else 3,
                "A questo livello il colloquio di system design è quasi garantito.",
            )
        for topic_id, (priority, why) in anchors.items():
            if topic_id in self.kb.topics:
                priorities[topic_id] = max(priorities.get(topic_id, 0), priority)
                rationales.setdefault(topic_id, why)

        return self._ensure_coding_practice(priorities, rationales, posting)

    def _ensure_coding_practice(
        self,
        priorities: dict[str, int],
        rationales: dict[str, str],
        posting: JobPosting,
    ) -> set[str]:
        """Decide su quali argomenti DSA il piano fa scrivere codice.

        Serve in due direzioni. Verso il basso: senza una garanzia, un annuncio
        molto orientato all'architettura spingerebbe fuori budget tutti i problemi
        DSA e il candidato arriverebbe al live coding senza averne risolto nemmeno
        uno. Verso l'alto: senza un tetto, il punteggio dell'annuncio può far
        emergere sei o sette argomenti DSA e riempire di esercizi anche il piano di
        un senior, dove il tempo serve al design. Restituisce quindi l'insieme -
        ampio quanto la quota - degli argomenti ammessi agli esercizi; gli altri
        restano nel piano come ripasso.
        """
        quota = DSA_QUOTA.get(posting.seniority, 2)
        risolvibili = [
            topic_id
            for topic_id in self.kb.topics
            if self.kb.topics[topic_id].category == "dsa"
            and self.kb.problems_by_topic.get(topic_id)
        ]
        if not risolvibili:
            return set()
        # Prima quelli che l'annuncio ha già fatto emergere, poi l'ordine di default.
        ordinati = sorted(
            risolvibili,
            key=lambda tid: (
                -priorities.get(tid, 0),
                DSA_FALLBACK_ORDER.index(tid) if tid in DSA_FALLBACK_ORDER else 99,
            ),
        )
        ammessi = set(ordinati[:quota])
        for topic_id in ammessi:
            priorities[topic_id] = max(priorities.get(topic_id, 0), 4)
            rationales.setdefault(
                topic_id,
                "Esercizio di codice: il colloquio tecnico ne prevede quasi sempre uno.",
            )
        return ammessi

    def _ensure_weak_areas(
        self,
        priorities: dict[str, int],
        rationales: dict[str, str],
        request: StudyPlanCreate,
    ) -> None:
        """Un'area dichiarata debole è esattamente ciò che va studiato per primo.

        Il solo peso nello scoring non basta: se l'annuncio non la nomina, il tema
        resterebbe in coda e verrebbe tagliato dal budget. Qui gli garantiamo una
        priorità alta, così sopravvive al taglio.
        """
        for weakness in request.weak_areas:
            scores = self.kb.score_topics([weakness])
            ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:3]
            for topic_id, _score in ranked:
                priorities[topic_id] = max(priorities.get(topic_id, 0), 4)
                rationales.setdefault(
                    topic_id,
                    f"Area che hai indicato come debole: {weakness}.",
                )

    # --- costruzione degli item --------------------------------------------

    def _build_items(
        self,
        priorities: dict[str, int],
        rationales: dict[str, str],
        request: StudyPlanCreate,
        esercizi_dsa: set[str],
    ) -> list[PlanItem]:
        items: list[PlanItem] = []
        ordered = sorted(priorities.items(), key=lambda kv: -kv[1])

        for topic_id, priority in ordered:
            topic = self.kb.topics[topic_id]
            rationale = rationales.get(topic_id, "")
            resources = [Resource(**r.model_dump()) for r in topic.resources]

            if (
                topic.track == "technical"
                and topic_id in esercizi_dsa
                and self.kb.problems_by_topic.get(topic_id)
            ):
                # Argomenti DSA entro la quota: si imparano scrivendo codice.
                for problem in self.kb.problems_for([topic_id])[:2]:
                    items.append(
                        PlanItem(
                            track="technical",
                            kind="coding",
                            title=f"Risolvi: {problem.title}",
                            topic_id=topic_id,
                            problem_id=problem.id,
                            rationale=rationale or f"Esercizio su {topic.title}.",
                            estimated_minutes=problem.estimated_minutes,
                            priority=priority,
                        )
                    )
                items.append(
                    PlanItem(
                        track="knowledge",
                        kind="study",
                        title=f"Ripassa: {topic.title}",
                        topic_id=topic_id,
                        rationale=rationale,
                        estimated_minutes=max(15, topic.estimated_minutes // 2),
                        priority=max(1, priority - 1),
                        resources=resources,
                    )
                )
                continue

            kind = KIND_BY_CATEGORY.get(topic.category, "study")
            track = "technical" if kind == "system_design" else "knowledge"
            items.append(
                PlanItem(
                    track=track,
                    kind=kind,
                    title=f"{TITLE_PREFIX[kind]}: {topic.title}",
                    topic_id=topic_id,
                    rationale=rationale,
                    estimated_minutes=topic.estimated_minutes,
                    priority=priority,
                    resources=resources,
                )
            )

            # Ogni argomento importante si verifica con un quiz: e' la parte tecnica
            # che l'utente ha chiesto esplicitamente.
            if priority >= 3 and self.kb.questions_by_topic.get(topic_id):
                items.append(
                    PlanItem(
                        track="technical",
                        kind="quiz",
                        title=f"Quiz: {topic.title}",
                        topic_id=topic_id,
                        rationale="Verifica di aver capito, non solo di aver letto.",
                        estimated_minutes=10,
                        priority=priority,
                    )
                )

        items.append(
            PlanItem(
                track="knowledge",
                kind="review",
                title="Ripasso finale e simulazione",
                rationale=(
                    "Ultimo giorno: rivedi le risposte modello degli argomenti a priorità 5, "
                    "ripeti le storie STAR ad alta voce e rileggi le domande da fare."
                ),
                estimated_minutes=min(60, request.daily_minutes),
                priority=5,
            )
        )
        return items

    def _fit_to_budget(self, items: list[PlanItem], request: StudyPlanCreate) -> list[PlanItem]:
        """Taglia il piano al tempo realmente disponibile, dalla priorità più bassa."""
        budget = request.days * request.daily_minutes
        final_review = [i for i in items if i.kind == "review"]
        reserved = sum(i.estimated_minutes for i in final_review)

        candidates = [i for i in items if i.kind != "review"]
        # A parità di priorità lo studio viene prima della verifica, poi i più corti:
        # un quiz da 10 minuti non deve rubare il posto all'argomento che verifica.
        candidates.sort(key=lambda i: (-i.priority, i.kind == "quiz", i.estimated_minutes))

        selected: list[PlanItem] = []
        studied: set[str] = set()
        used = reserved
        for item in candidates:
            if used + item.estimated_minutes > budget:
                continue
            # Un quiz su un argomento che non è nel piano non serve a niente:
            # senza questo controllo il budget si riempie di verifiche orfane.
            if item.kind == "quiz" and item.topic_id not in studied:
                continue
            selected.append(item)
            used += item.estimated_minutes
            if item.track == "knowledge" and item.topic_id:
                studied.add(item.topic_id)
        return selected + final_review

    @staticmethod
    def _assign_days(items: list[PlanItem], request: StudyPlanCreate) -> None:
        """Distribuisce gli item sui giorni rispettando il budget giornaliero.

        Si cambia giorno quando la quota è esaurita, non quando il prossimo item
        non ci sta: altrimenti gli avanzi si accumulano tutti sull'ultimo giorno.
        L'ultimo giorno tiene da parte lo spazio per il ripasso finale.
        """
        last_day = max(1, request.days)
        review = [i for i in items if i.kind == "review"]
        for item in review:
            item.day = last_day
        reserved = sum(i.estimated_minutes for i in review)

        rest = [i for i in items if i.kind != "review"]
        # Priorità alta nei primi giorni: se l'utente si ferma prima, ha fatto il grosso.
        rest.sort(key=lambda i: (-i.priority, i.track != "knowledge", i.title))
        rest = StudyPlanBuilder._break_runs(StudyPlanBuilder._interleave_tracks(rest))

        day = 1
        used = 0
        for item in rest:
            quota = request.daily_minutes - (reserved if day == last_day else 0)
            if used >= max(quota, 1) and day < last_day:
                day += 1
                used = 0
            item.day = day
            used += item.estimated_minutes

    @staticmethod
    def _interleave_tracks(items: list[PlanItem]) -> list[PlanItem]:
        """Alterna teoria e pratica dentro ogni fascia di priorità.

        Senza questo una giornata può diventare sei quiz di fila: le attività
        restano le stesse ma la sequenza è molto meno sostenibile da seguire.
        """
        out: list[PlanItem] = []
        for priority in sorted({i.priority for i in items}, reverse=True):
            gruppo = [i for i in items if i.priority == priority]
            knowledge = [i for i in gruppo if i.track == "knowledge"]
            technical = [i for i in gruppo if i.track == "technical"]
            while knowledge or technical:
                if knowledge:
                    out.append(knowledge.pop(0))
                if technical:
                    out.append(technical.pop(0))
        return out

    MAX_RUN = 4

    @staticmethod
    def _break_runs(items: list[PlanItem], max_run: int = MAX_RUN) -> list[PlanItem]:
        """Spezza le sequenze troppo lunghe dello stesso tipo.

        L'alternanza dentro la fascia di priorità non basta: se in una fascia
        finiscono solo argomenti teorici, la sequenza lunga ricompare comunque.
        Qui, quando una sequenza supera il limite, si tira avanti l'attività più
        vicina dell'altro tipo, spostandola di poco rispetto alla priorità. Se
        l'altro tipo non c'è proprio, la sequenza resta: non si inventa varietà
        che il piano non ha.
        """
        out: list[PlanItem] = []
        rimasti = list(items)
        corsa = 0
        while rimasti:
            scelto = 0
            if out and corsa >= max_run and rimasti[0].track == out[-1].track:
                for indice, candidato in enumerate(rimasti):
                    if candidato.track != out[-1].track:
                        scelto = indice
                        break
            item = rimasti.pop(scelto)
            corsa = corsa + 1 if out and out[-1].track == item.track else 1
            out.append(item)
        return out

    # --- testi di fallback --------------------------------------------------

    @staticmethod
    def _plan_title(posting: JobPosting) -> str:
        role = posting.role_title or "Posizione software developer"
        if not posting.company_name:
            return role
        # Il titolo estratto dall'annuncio contiene spesso già il nome dell'azienda
        # ("Senior Backend Engineer - Acme Pay"): non va ripetuto.
        if normalize(posting.company_name) in normalize(role):
            return role
        return f"{role} - {posting.company_name}"

    @staticmethod
    def _job_summary(posting: JobPosting) -> str:
        parts = [
            f"Ruolo: {posting.role_title or 'non specificato'}",
            f"Azienda: {posting.company_name or 'non specificata'}",
            f"Seniority: {posting.seniority}",
            f"Stack: {', '.join(posting.tech_stack) or 'non specificato'}",
        ]
        if posting.requirements:
            top = sorted(posting.requirements, key=lambda r: -r.importance)[:10]
            parts.append(
                "Requisiti chiave: "
                + ", ".join(f"{r.name} (importanza {r.importance}/5)" for r in top)
            )
        if posting.responsibilities:
            parts.append("Responsabilità: " + "; ".join(posting.responsibilities[:6]))
        return "\n".join(parts)

    @staticmethod
    def _heuristic_focus(posting: JobPosting) -> list[str]:
        focus = list(posting.interview_focus[:4]) or posting.tech_stack[:4]
        if posting.seniority in {"senior", "staff"}:
            focus.append("System design e trade-off architetturali")
        else:
            focus.append("Algoritmi e strutture dati")
        focus.append("Domande comportamentali con metodo STAR")
        return focus[:6]

    def _heuristic_gaps(self, posting: JobPosting, request: StudyPlanCreate) -> list[str]:
        gaps: list[str] = []
        known = {normalize(s) for s in request.known_strengths}
        for requirement in sorted(posting.requirements, key=lambda r: -r.importance):
            if requirement.importance >= 4 and normalize(requirement.name) not in known:
                gaps.append(
                    f"{requirement.name}: richiesto con importanza {requirement.importance}/5 "
                    "e non presente fra i punti di forza dichiarati."
                )
        if not posting.requirements:
            gaps.append(
                "L'annuncio è generico: conviene chiedere al recruiter su cosa verterà "
                "il colloquio tecnico."
            )
        return gaps[:8]

    @staticmethod
    def _heuristic_summary(posting: JobPosting, request: StudyPlanCreate) -> str:
        budget = request.days * request.daily_minutes
        return (
            f"Piano da {request.days} giorni ({budget} minuti totali) per "
            f"{posting.role_title or 'la posizione'}"
            f"{' in ' + posting.company_name if posting.company_name else ''}. "
            "Gli argomenti sono ordinati per priorità: i primi giorni coprono ciò che "
            "l'annuncio rende più probabile in sede di colloquio, l'ultimo giorno è "
            "dedicato al ripasso. La parte conoscitiva serve a saper raccontare gli "
            "argomenti, quella tecnica a dimostrarli con quiz e codice."
        )


def plan_progress_by_track(plan: StudyPlan) -> dict[str, dict]:
    """Statistiche separate per i due binari, usate dalla dashboard."""
    out: dict[str, dict] = {}
    for track in ("knowledge", "technical"):
        items = [i for i in plan.items if i.track == track]
        done = [i for i in items if i.status == "done"]
        out[track] = {
            "total": len(items),
            "done": len(done),
            "minutes": sum(i.estimated_minutes for i in items),
            "minutes_done": sum(i.estimated_minutes for i in done),
            "percent": round(len(done) / len(items) * 100) if items else 0,
        }
    return out


def plan_by_day(plan: StudyPlan) -> list[dict]:
    days: dict[int, list[PlanItem]] = {}
    for item in plan.items:
        days.setdefault(item.day, []).append(item)
    out = []
    for day in sorted(days):
        items = days[day]
        out.append(
            {
                "day": day,
                "date": _day_date(plan, day),
                "minutes": sum(i.estimated_minutes for i in items),
                "items": [i.model_dump(mode="json") for i in items],
            }
        )
    return out


def _day_date(plan: StudyPlan, day: int) -> str | None:
    """Converte il numero di giorno in una data reale, se conosciamo quella del colloquio."""
    if not plan.interview_date:
        return None
    from datetime import timedelta

    start = plan.interview_date - timedelta(days=plan.days)
    result: date = start + timedelta(days=day)
    return result.isoformat()
