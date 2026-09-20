"""Analisi dell'annuncio di lavoro e scheda azienda.

Con l'AI configurata si usa il modello per l'estrazione strutturata; senza,
si ricade su un'euristica che riconosce le tecnologie note e le frasi chiave.
L'app resta quindi utilizzabile anche a costo zero.
"""

from __future__ import annotations

import logging
import re

from ..ai import prompts
from ..ai.client import AIClient
from ..domain.models import CompanyProfile, JobPosting, JobRequirement, Seniority
from .knowledge import normalize, tokenize

logger = logging.getLogger(__name__)

# Dizionario di tecnologie riconosciute dall'euristica di fallback.
# La chiave e' la forma normalizzata cercata nel testo, il valore l'etichetta mostrata.
TECH_DICTIONARY: dict[str, tuple[str, str]] = {
    # linguaggi
    "python": ("Python", "linguaggio"),
    "java": ("Java", "linguaggio"),
    "kotlin": ("Kotlin", "linguaggio"),
    "javascript": ("JavaScript", "linguaggio"),
    "typescript": ("TypeScript", "linguaggio"),
    "golang": ("Go", "linguaggio"),
    "rust": ("Rust", "linguaggio"),
    "c#": ("C#", "linguaggio"),
    "csharp": ("C#", "linguaggio"),
    "php": ("PHP", "linguaggio"),
    "ruby": ("Ruby", "linguaggio"),
    "scala": ("Scala", "linguaggio"),
    "swift": ("Swift", "linguaggio"),
    # framework
    "django": ("Django", "framework"),
    "flask": ("Flask", "framework"),
    "fastapi": ("FastAPI", "framework"),
    "spring": ("Spring", "framework"),
    "express": ("Express", "framework"),
    "nestjs": ("NestJS", "framework"),
    "react": ("React", "framework"),
    "angular": ("Angular", "framework"),
    "vue": ("Vue", "framework"),
    "next.js": ("Next.js", "framework"),
    "nextjs": ("Next.js", "framework"),
    "node.js": ("Node.js", "framework"),
    "nodejs": ("Node.js", "framework"),
    "dotnet": (".NET", "framework"),
    ".net": (".NET", "framework"),
    "laravel": ("Laravel", "framework"),
    "rails": ("Ruby on Rails", "framework"),
    # dati
    "postgresql": ("PostgreSQL", "database"),
    "postgres": ("PostgreSQL", "database"),
    "mysql": ("MySQL", "database"),
    "mariadb": ("MariaDB", "database"),
    "mongodb": ("MongoDB", "database"),
    "redis": ("Redis", "database"),
    "elasticsearch": ("Elasticsearch", "database"),
    "cassandra": ("Cassandra", "database"),
    "dynamodb": ("DynamoDB", "database"),
    "sqlserver": ("SQL Server", "database"),
    "oracle": ("Oracle", "database"),
    "snowflake": ("Snowflake", "database"),
    "clickhouse": ("ClickHouse", "database"),
    # infrastruttura
    "docker": ("Docker", "cloud"),
    "kubernetes": ("Kubernetes", "cloud"),
    "k8s": ("Kubernetes", "cloud"),
    "terraform": ("Terraform", "cloud"),
    "ansible": ("Ansible", "cloud"),
    "aws": ("AWS", "cloud"),
    "azure": ("Azure", "cloud"),
    "gcp": ("GCP", "cloud"),
    "openshift": ("OpenShift", "cloud"),
    "jenkins": ("Jenkins", "cloud"),
    "gitlab": ("GitLab CI", "cloud"),
    "github": ("GitHub Actions", "cloud"),
    "argocd": ("ArgoCD", "cloud"),
    # messaggistica e architettura
    "kafka": ("Kafka", "architettura"),
    "rabbitmq": ("RabbitMQ", "architettura"),
    "sqs": ("SQS", "architettura"),
    "servicebus": ("Service Bus", "architettura"),
    "graphql": ("GraphQL", "architettura"),
    "grpc": ("gRPC", "architettura"),
    "rest": ("REST", "architettura"),
    "microservizi": ("Microservizi", "architettura"),
    "microservices": ("Microservizi", "architettura"),
    "serverless": ("Serverless", "architettura"),
    "ddd": ("Domain-Driven Design", "architettura"),
    "cqrs": ("CQRS", "architettura"),
    # pratiche
    "ci/cd": ("CI/CD", "testing"),
    "cicd": ("CI/CD", "testing"),
    "tdd": ("TDD", "testing"),
    "pytest": ("pytest", "testing"),
    "junit": ("JUnit", "testing"),
    "jest": ("Jest", "testing"),
    "cypress": ("Cypress", "testing"),
    "agile": ("Agile", "soft-skill"),
    "scrum": ("Scrum", "soft-skill"),
    "kanban": ("Kanban", "soft-skill"),
    "git": ("Git", "testing"),
}

# L'ordine conta: si applica il primo pattern che matcha. Gli intervalli espliciti
# ("3-5 anni") vanno controllati prima dei pattern senior, altrimenti il "5 anni"
# contenuto nell'intervallo li dirotterebbe su "senior".
SENIORITY_PATTERNS: list[tuple[str, Seniority]] = [
    (r"\b(stage|stagista|intern|internship|tirocin)", "intern"),
    (r"\b(junior|jr\.?|entry[- ]level|neo[- ]?laureat|0-2 anni|1-2 anni)", "junior"),
    (r"\b(staff engineer|principal|architect|tech lead|lead engineer)", "staff"),
    (r"(\bmid[- ]level|\bmiddle\b|\d\s*-\s*\d\s*anni|\b3\+?\s*anni)", "mid"),
    (r"(\bsenior|\bsr\.\s|(?<![\d-])[5-9]\+?\s*anni|\besperienza pluriennale|"
     r"(?<![\d-])1[0-9]\+?\s*anni)", "senior"),
]

WORK_MODE_PATTERNS: list[tuple[str, str]] = [
    (r"\b(full[- ]?remote|100% remoto|completamente da remoto)", "full remote"),
    (r"\b(ibrid[aeio]|hybrid)", "ibrido"),
    (r"\b(on[- ]?site|in sede|presenza)", "on-site"),
    (r"\b(remoto|remote|smart working)", "remoto"),
]

ITALIAN_CITIES = [
    "milano", "roma", "torino", "napoli", "bologna", "firenze", "padova", "verona",
    "genova", "bari", "catania", "palermo", "venezia", "trento", "bolzano", "pisa",
    "modena", "parma", "brescia", "bergamo", "vicenza", "trieste", "perugia", "cagliari",
]


def _first_match(patterns: list[tuple[str, str]], text: str) -> str:
    for pattern, label in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return ""


def _extract_bullets(raw_text: str, keywords: list[str], limit: int = 8) -> list[str]:
    """Raccoglie le righe elenco che seguono un'intestazione contenente una keyword."""
    lines = [line.strip() for line in raw_text.splitlines()]
    collected: list[str] = []
    capturing = False
    for line in lines:
        stripped = line.lstrip("-*•·–— \t")
        if not stripped:
            if collected:
                capturing = False
            continue
        lowered = normalize(stripped)
        is_bullet = bool(re.match(r"^[-*•·–—]\s*", line)) or bool(re.match(r"^\d+[.)]\s", line))
        if any(keyword in lowered for keyword in keywords) and len(stripped) < 120:
            capturing = True
            continue
        if capturing and is_bullet:
            collected.append(stripped.rstrip(";.,"))
            if len(collected) >= limit:
                break
    return collected


class JobAnalyzer:
    """Estrae dall'annuncio i dati che servono a costruire il piano."""

    def __init__(self, ai: AIClient) -> None:
        self.ai = ai

    async def analyze(
        self,
        raw_text: str,
        *,
        source_url: str = "",
        company_name: str = "",
        notes: str = "",
    ) -> JobPosting:
        posting = self.heuristic_analysis(raw_text)
        posting.source_url = source_url
        if company_name:
            posting.company_name = company_name

        if self.ai.available:
            try:
                data = await self.ai.complete_json(
                    prompts.JOB_ANALYSIS_SYSTEM,
                    prompts.job_analysis_user(raw_text, notes),
                    schema=prompts.JOB_ANALYSIS_SCHEMA,
                    schema_name="analisi_annuncio",
                )
                posting = self._merge_ai(posting, data, company_name)
                posting.analyzed_with_ai = True
            except Exception as exc:
                # L'euristica ha gia' prodotto un risultato usabile: non falliamo.
                logger.warning("Analisi AI fallita, resto sull'euristica: %s", exc)
        return posting

    # --- euristica ----------------------------------------------------------

    @staticmethod
    def heuristic_analysis(raw_text: str) -> JobPosting:
        text = raw_text.strip()
        normalized = normalize(text)
        tokens = set(tokenize(text))

        stack: list[str] = []
        requirements: list[JobRequirement] = []
        seen_labels: set[str] = set()
        for needle, (label, category) in TECH_DICTIONARY.items():
            # I token coprono le parole singole, la ricerca diretta le forme con punti e slash.
            found = needle in tokens or (
                not needle.isalnum() and needle in normalized
            )
            if not found or label in seen_labels:
                continue
            seen_labels.add(label)
            stack.append(label)
            occurrences = normalized.count(needle)
            importance = 5 if occurrences >= 3 else 4 if occurrences == 2 else 3
            requirements.append(
                JobRequirement(name=label, category=category, importance=importance)
            )

        role_title = ""
        for line in text.splitlines():
            candidate = line.strip()
            if 5 < len(candidate) < 90 and re.search(
                r"(developer|engineer|sviluppatore|programmatore|architect|analyst|devops|sre)",
                candidate,
                re.IGNORECASE,
            ):
                role_title = candidate.lstrip("#*-• ").strip()
                break

        location = next((city.capitalize() for city in ITALIAN_CITIES if city in normalized), "")

        return JobPosting(
            raw_text=text,
            role_title=role_title,
            seniority=_first_match(SENIORITY_PATTERNS, text) or "unknown",  # type: ignore
            location=location,
            work_mode=_first_match(WORK_MODE_PATTERNS, text),
            tech_stack=stack,
            requirements=requirements,
            responsibilities=_extract_bullets(
                text, ["responsabilita", "cosa farai", "ruolo", "attivita", "what you will do"]
            ),
            nice_to_have=_extract_bullets(
                text, ["nice to have", "gradito", "plus", "preferenziale", "costituisce titolo"]
            ),
            interview_focus=stack[:5],
        )

    # --- fusione con la risposta del modello --------------------------------

    @staticmethod
    def _merge_ai(base: JobPosting, data: dict, company_override: str) -> JobPosting:
        def pick_list(key: str, fallback: list) -> list:
            value = data.get(key)
            return value if isinstance(value, list) and value else fallback

        requirements: list[JobRequirement] = []
        for row in data.get("requirements") or []:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            try:
                importance = int(row.get("importance", 3))
            except (TypeError, ValueError):
                importance = 3
            requirements.append(
                JobRequirement(
                    name=str(row["name"])[:80],
                    category=str(row.get("category", "general"))[:40],
                    importance=max(1, min(5, importance)),
                    evidence=str(row.get("evidence", ""))[:300],
                )
            )

        seniority = str(data.get("seniority") or "").lower()
        valid_seniority = {"intern", "junior", "mid", "senior", "staff", "unknown"}

        base.company_name = company_override or str(data.get("company_name") or base.company_name)
        base.role_title = str(data.get("role_title") or base.role_title)
        if seniority in valid_seniority and seniority != "unknown":
            base.seniority = seniority  # type: ignore[assignment]
        base.location = str(data.get("location") or base.location)
        base.work_mode = str(data.get("work_mode") or base.work_mode)
        base.tech_stack = [str(s)[:60] for s in pick_list("tech_stack", base.tech_stack)][:30]
        base.requirements = requirements or base.requirements
        base.nice_to_have = [
            str(s)[:200] for s in pick_list("nice_to_have", base.nice_to_have)
        ][:15]
        base.responsibilities = [
            str(s)[:300] for s in pick_list("responsibilities", base.responsibilities)
        ][:15]
        base.interview_focus = [
            str(s)[:200] for s in pick_list("interview_focus", base.interview_focus)
        ][:12]
        base.red_flags = [str(s)[:300] for s in (data.get("red_flags") or [])][:8]
        return base

    # --- scheda azienda -----------------------------------------------------

    async def research_company(self, posting: JobPosting) -> CompanyProfile:
        profile = CompanyProfile(name=posting.company_name)
        if not self.ai.available:
            profile.research_notes = (
                "AI non configurata: la scheda azienda va compilata a mano. "
                "Controlla sito, pagina careers, engineering blog, LinkedIn e notizie "
                "degli ultimi 6-12 mesi."
            )
            profile.questions_to_ask = DEFAULT_QUESTIONS_TO_ASK.copy()
            return profile

        try:
            data = await self.ai.complete_json(
                prompts.COMPANY_SYSTEM,
                prompts.company_user(
                    posting.company_name, posting.role_title, posting.raw_text
                ),
                schema=prompts.COMPANY_SCHEMA,
                schema_name="scheda_azienda",
                temperature=0.4,
            )
        except Exception as exc:
            logger.warning("Ricerca azienda fallita: %s", exc)
            profile.questions_to_ask = DEFAULT_QUESTIONS_TO_ASK.copy()
            profile.research_notes = f"Ricerca automatica non riuscita: {exc}"
            return profile

        def as_list(key: str, limit: int = 10) -> list[str]:
            value = data.get(key)
            return [str(v)[:300] for v in value][:limit] if isinstance(value, list) else []

        profile.industry = str(data.get("industry", ""))[:120]
        profile.size = str(data.get("size", ""))[:120]
        profile.products = as_list("products")
        profile.tech_culture = str(data.get("tech_culture", ""))[:1500]
        profile.interview_process = as_list("interview_process")
        profile.talking_points = as_list("talking_points")
        profile.questions_to_ask = as_list("questions_to_ask") or DEFAULT_QUESTIONS_TO_ASK.copy()
        profile.research_notes = str(data.get("research_notes", ""))[:2000]
        profile.ai_generated = True
        return profile


DEFAULT_QUESTIONS_TO_ASK = [
    "Come nascono le priorità del team e chi decide su cosa si lavora il prossimo trimestre?",
    "Com'è il ciclo di rilascio: quanto passa da un merge alla produzione?",
    "Qual è stato l'ultimo incidente significativo e cosa è cambiato dopo?",
    "Come è distribuito il tempo fra nuove funzionalità, manutenzione e debito tecnico?",
    "Che aspetto ha una buona performance in questo ruolo dopo sei mesi?",
]
