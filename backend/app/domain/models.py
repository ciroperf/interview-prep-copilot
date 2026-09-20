"""Modelli di dominio condivisi da API, servizi e storage."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Track = Literal["knowledge", "technical"]
ItemKind = Literal["study", "quiz", "coding", "behavioral", "company", "system_design", "review"]
Difficulty = Literal["easy", "medium", "hard"]
Seniority = Literal["intern", "junior", "mid", "senior", "staff", "unknown"]
ItemStatus = Literal["todo", "in_progress", "done", "skipped"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Knowledge base (contenuti statici, versionati in YAML)
# ---------------------------------------------------------------------------


class Resource(BaseModel):
    title: str
    url: str = ""
    kind: Literal["article", "video", "book", "doc", "practice"] = "article"


class Example(BaseModel):
    """Un esempio concreto: codice, query, configurazione o traccia di richiesta.

    Serve a rendere verificabile la spiegazione: si legge, si prova, si capisce
    se si era capito.
    """

    title: str
    code: str
    language: str = "text"
    note: str = ""


class TradeOff(BaseModel):
    """Un'alternativa progettuale con il suo prezzo.

    Ai colloqui la domanda vera non è mai "cos'è X" ma "perché X e non Y": senza
    il prezzo di ogni opzione non c'è una scelta, c'è una preferenza.
    """

    option: str
    pros: str
    cons: str
    when: str = ""


class FollowUp(BaseModel):
    """Una domanda di approfondimento con la traccia della risposta."""

    question: str
    answer: str = ""


class Topic(BaseModel):
    """Un argomento della base di conoscenza, con la risposta modello da colloquio."""

    id: str
    title: str
    category: str
    track: Track = "technical"
    level: Difficulty = "medium"
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    # La spiegazione lunga: è la parte da studiare, non da ripassare. Vuota
    # sugli argomenti generati al volo da un annuncio, dove conta arrivare
    # subito al sodo.
    deep_dive: str = ""
    key_points: list[str] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    trade_offs: list[TradeOff] = Field(default_factory=list)
    # Ordini di grandezza da avere in testa: al colloquio un numero detto con
    # sicurezza vale più di tre frasi di contorno.
    numbers: list[str] = Field(default_factory=list)
    interview_answer: str = ""
    # Cosa distingue la risposta di chi ha visto il problema in produzione.
    senior_signals: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    follow_ups: list[FollowUp] = Field(default_factory=list)
    # Forma storica, senza risposta: la usano ancora gli argomenti generati
    # dall'AI a partire da un annuncio.
    follow_up_questions: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    estimated_minutes: int = 25
    # True per gli argomenti aggiunti a runtime partendo da un annuncio:
    # vivono nello storage, non nei file YAML del repository.
    custom: bool = False
    created_at: datetime | None = None
    source_term: str = ""


class QuizQuestion(BaseModel):
    id: str
    topic_id: str
    prompt: str
    options: list[str]
    answer_index: int
    explanation: str = ""
    difficulty: Difficulty = "medium"
    tags: list[str] = Field(default_factory=list)
    generated: bool = False

    def public(self) -> QuizQuestionPublic:
        """Versione senza soluzione, da mandare al client."""
        return QuizQuestionPublic(
            id=self.id,
            topic_id=self.topic_id,
            prompt=self.prompt,
            options=self.options,
            difficulty=self.difficulty,
            tags=self.tags,
        )


class QuizQuestionPublic(BaseModel):
    id: str
    topic_id: str
    prompt: str
    options: list[str]
    difficulty: Difficulty = "medium"
    tags: list[str] = Field(default_factory=list)


class CodingTestCase(BaseModel):
    kwargs: dict = Field(default_factory=dict)
    expected: object = None
    # Alcuni problemi (es. "ordine non garantito") vanno confrontati come insiemi.
    compare: Literal["equal", "set", "sorted"] = "equal"
    hidden: bool = False


class CodingProblem(BaseModel):
    id: str
    title: str
    topic_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: Difficulty = "medium"
    statement: str
    function_name: str
    starter_code: str
    examples: list[str] = Field(default_factory=list)
    tests: list[CodingTestCase] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    solution: str = ""
    target_complexity: str = ""
    estimated_minutes: int = 30

    def public(self) -> dict:
        """Nasconde soluzione e test marcati come nascosti."""
        data = self.model_dump()
        data.pop("solution", None)
        data["tests"] = [t for t in data.get("tests", []) if not t.get("hidden")]
        return data


# ---------------------------------------------------------------------------
# Job posting e azienda
# ---------------------------------------------------------------------------


class JobRequirement(BaseModel):
    """Una singola competenza richiesta, con il peso che le diamo nel piano."""

    name: str
    category: str = "general"
    importance: int = Field(default=3, ge=1, le=5)
    evidence: str = ""


class CompanyProfile(BaseModel):
    name: str = ""
    industry: str = ""
    size: str = ""
    products: list[str] = Field(default_factory=list)
    tech_culture: str = ""
    interview_process: list[str] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    research_notes: str = ""
    ai_generated: bool = False


class JobPosting(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: new_id("job"))
    created_at: datetime = Field(default_factory=utcnow)
    raw_text: str = ""
    source_url: str = ""

    company_name: str = ""
    role_title: str = ""
    seniority: Seniority = "unknown"
    location: str = ""
    work_mode: str = ""
    language: str = "it"

    tech_stack: list[str] = Field(default_factory=list)
    requirements: list[JobRequirement] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)

    company: CompanyProfile = Field(default_factory=CompanyProfile)
    analyzed_with_ai: bool = False


class JobPostingCreate(BaseModel):
    raw_text: str = Field(min_length=30, description="Testo integrale dell'annuncio")
    source_url: str = ""
    company_name: str = ""
    notes: str = ""
    research_company: bool = True


# ---------------------------------------------------------------------------
# Piano di studi
# ---------------------------------------------------------------------------


class PlanItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("item"))
    day: int = 1
    track: Track = "technical"
    kind: ItemKind = "study"
    title: str
    topic_id: str = ""
    problem_id: str = ""
    rationale: str = ""
    estimated_minutes: int = 25
    priority: int = Field(default=3, ge=1, le=5)
    status: ItemStatus = "todo"
    completed_at: datetime | None = None
    resources: list[Resource] = Field(default_factory=list)


class StudyPlan(BaseModel):
    id: str = Field(default_factory=lambda: new_id("plan"))
    job_id: str
    created_at: datetime = Field(default_factory=utcnow)
    title: str = ""
    summary: str = ""
    interview_date: date | None = None
    days: int = 7
    daily_minutes: int = 90
    items: list[PlanItem] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    gap_analysis: list[str] = Field(default_factory=list)
    ai_generated: bool = False

    @property
    def total_minutes(self) -> int:
        return sum(item.estimated_minutes for item in self.items)

    def progress(self) -> dict:
        total = len(self.items)
        done = sum(1 for item in self.items if item.status == "done")
        skipped = sum(1 for item in self.items if item.status == "skipped")
        actionable = max(total - skipped, 0)
        return {
            "total": total,
            "done": done,
            "skipped": skipped,
            "percent": round(done / actionable * 100) if actionable else 0,
            "minutes_total": self.total_minutes,
            "minutes_done": sum(i.estimated_minutes for i in self.items if i.status == "done"),
        }


class StudyPlanCreate(BaseModel):
    job_id: str
    days: int = Field(default=7, ge=1, le=60)
    daily_minutes: int = Field(default=90, ge=20, le=600)
    interview_date: date | None = None
    # Competenze che l'utente sa gia' di avere: abbassano la priorita' dei temi collegati.
    known_strengths: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    use_ai: bool = True


class PlanItemUpdate(BaseModel):
    status: ItemStatus


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------


class QuizCreate(BaseModel):
    job_id: str = ""
    plan_id: str = ""
    topic_ids: list[str] = Field(default_factory=list)
    num_questions: int = Field(default=10, ge=1, le=40)
    difficulty: Difficulty | None = None
    use_ai: bool = False


class QuizAnswer(BaseModel):
    question_id: str
    selected_index: int


class QuizSubmission(BaseModel):
    answers: list[QuizAnswer] = Field(default_factory=list)


class GradedAnswer(BaseModel):
    question_id: str
    prompt: str
    selected_index: int
    answer_index: int
    correct: bool
    explanation: str = ""
    topic_id: str = ""


class Quiz(BaseModel):
    id: str = Field(default_factory=lambda: new_id("quiz"))
    created_at: datetime = Field(default_factory=utcnow)
    job_id: str = ""
    plan_id: str = ""
    questions: list[QuizQuestion] = Field(default_factory=list)
    submitted_at: datetime | None = None
    score: int | None = None
    graded: list[GradedAnswer] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Esercizi di coding
# ---------------------------------------------------------------------------


class CodeSubmission(BaseModel):
    problem_id: str
    code: str = Field(min_length=1, max_length=40_000)
    language: Literal["python"] = "python"


class TestOutcome(BaseModel):
    name: str
    passed: bool
    expected: str = ""
    actual: str = ""
    error: str = ""


class CodeReview(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sub"))
    created_at: datetime = Field(default_factory=utcnow)
    problem_id: str
    executed: bool = False
    tests_passed: int = 0
    tests_total: int = 0
    outcomes: list[TestOutcome] = Field(default_factory=list)
    verdict: str = ""
    correctness: str = ""
    complexity: str = ""
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    interview_notes: str = ""
    ai_generated: bool = False


# ---------------------------------------------------------------------------
# CV
# ---------------------------------------------------------------------------


class CvBulletRewrite(BaseModel):
    original: str
    improved: str
    why: str = ""


class TopicGap(BaseModel):
    """Una competenza richiesta dall'annuncio e non coperta dal catalogo."""

    term: str
    importance: int = 3
    covered: bool = False
    coverage_score: float = 0.0
    best_topic_id: str = ""
    best_topic_title: str = ""


class TopicDraft(BaseModel):
    """Contenuto di un argomento scritto a mano, quando non si vuole usare l'AI."""

    title: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=20)
    category: str = "custom"
    track: Track = "knowledge"
    level: Difficulty = "medium"
    tags: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    interview_answer: str = ""
    pitfalls: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    estimated_minutes: int = Field(default=30, ge=5, le=240)


class TopicCreate(BaseModel):
    """Richiesta di aggiunta di un argomento alla knowledge base."""

    term: str = Field(min_length=2, max_length=80, description="Es. Kubernetes")
    job_id: str = ""
    category: str = ""
    num_questions: int = Field(default=3, ge=0, le=8)
    # Se valorizzato, l'argomento viene creato da questo contenuto senza chiamare l'AI.
    draft: TopicDraft | None = None


class CvReview(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cv"))
    created_at: datetime = Field(default_factory=utcnow)
    job_id: str = ""
    filename: str = ""
    char_count: int = 0
    blob_path: str = ""

    overall_score: int = Field(default=0, ge=0, le=100)
    summary: str = ""
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    bullet_rewrites: list[CvBulletRewrite] = Field(default_factory=list)
    tailored_summary: str = ""
    likely_questions: list[str] = Field(default_factory=list)
    ai_generated: bool = False
