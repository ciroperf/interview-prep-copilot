"""Caricamento del CV, analisi delle parole chiave e revisione mirata sull'annuncio."""

from __future__ import annotations

import io
import logging
import re

from ..ai import prompts
from ..ai.client import AIClient
from ..domain.models import CvBulletRewrite, CvReview, JobPosting
from .jobs import TECH_DICTIONARY
from .knowledge import normalize, tokenize

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# Verbi d'azione che rendono forte un bullet di CV.
ACTION_VERBS = {
    "progettato", "sviluppato", "implementato", "ottimizzato", "ridotto", "aumentato",
    "migrato", "automatizzato", "guidato", "coordinato", "rifattorizzato", "integrato",
    "migliorato", "realizzato", "introdotto", "scalato", "risolto", "costruito",
    "built", "designed", "implemented", "reduced", "improved", "led", "migrated",
    "automated", "increased", "optimized", "shipped", "delivered", "scaled",
}


class CvExtractionError(ValueError):
    """Il file caricato non è leggibile come testo."""


def extract_text(filename: str, data: bytes) -> str:
    """Estrae il testo da PDF, DOCX, TXT o Markdown."""
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in SUPPORTED_EXTENSIONS:
        raise CvExtractionError(
            f"Formato non supportato: {suffix or 'sconosciuto'}. "
            f"Accettati: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
        except Exception as exc:
            raise CvExtractionError(f"PDF non leggibile: {exc}") from exc
        if not text.strip():
            raise CvExtractionError(
                "Il PDF non contiene testo estraibile: sembra una scansione. "
                "Esporta il CV come PDF testuale oppure caricalo in .docx o .txt."
            )
        return text

    if suffix == ".docx":
        try:
            import docx

            document = docx.Document(io.BytesIO(data))
            parts = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    parts.extend(cell.text for cell in row.cells)
            return "\n".join(parts)
        except CvExtractionError:
            raise
        except Exception as exc:
            raise CvExtractionError(f"DOCX non leggibile: {exc}") from exc

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def job_keywords(posting: JobPosting) -> list[str]:
    """Parole chiave dell'annuncio da cercare nel CV."""
    keywords: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        cleaned = value.strip()
        key = normalize(cleaned)
        if cleaned and key and key not in seen and len(cleaned) < 40:
            seen.add(key)
            keywords.append(cleaned)

    for item in posting.tech_stack:
        add(item)
    for requirement in sorted(posting.requirements, key=lambda r: -r.importance):
        add(requirement.name)
    # Dal testo grezzo recuperiamo le tecnologie note non finite nello stack.
    normalized_text = normalize(posting.raw_text)
    text_tokens = set(tokenize(posting.raw_text))
    for needle, (label, _category) in TECH_DICTIONARY.items():
        if needle in text_tokens or (not needle.isalnum() and needle in normalized_text):
            add(label)
    return keywords[:40]


def keyword_gap(cv_text: str, posting: JobPosting) -> tuple[list[str], list[str]]:
    """Divide le parole chiave dell'annuncio fra presenti e assenti nel CV."""
    cv_normalized = normalize(cv_text)
    cv_tokens = set(tokenize(cv_text))
    matched: list[str] = []
    missing: list[str] = []
    for keyword in job_keywords(posting):
        key = normalize(keyword)
        found = key in cv_tokens or key in cv_normalized
        (matched if found else missing).append(keyword)
    return matched, missing


def extract_bullets(cv_text: str, limit: int = 25) -> list[str]:
    bullets: list[str] = []
    for line in cv_text.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*•·–—]\s+", stripped) and len(stripped) > 15:
            bullets.append(stripped.lstrip("-*•·–— ").strip())
        if len(bullets) >= limit:
            break
    return bullets


class CvService:
    def __init__(self, ai: AIClient) -> None:
        self.ai = ai

    async def review(
        self, cv_text: str, posting: JobPosting | None, filename: str = ""
    ) -> CvReview:
        review = CvReview(
            job_id=posting.id if posting else "",
            filename=filename,
            char_count=len(cv_text),
        )
        if posting:
            review.matched_keywords, review.missing_keywords = keyword_gap(cv_text, posting)

        if self.ai.available:
            try:
                data = await self.ai.complete_json(
                    prompts.CV_SYSTEM,
                    prompts.cv_user(
                        cv_text,
                        self._job_summary(posting),
                        review.missing_keywords,
                    ),
                    schema=prompts.CV_SCHEMA,
                    schema_name="revisione_cv",
                    temperature=0.4,
                )
                self._apply_ai(review, data)
                return review
            except Exception as exc:
                logger.warning("Revisione AI del CV fallita: %s", exc)

        self._heuristic_review(review, cv_text, posting)
        return review

    @staticmethod
    def _job_summary(posting: JobPosting | None) -> str:
        if posting is None:
            return (
                "Nessun annuncio associato: valuta il CV per una posizione generica "
                "da software developer."
            )
        lines = [
            f"Ruolo: {posting.role_title or 'non specificato'}",
            f"Azienda: {posting.company_name or 'non specificata'}",
            f"Seniority: {posting.seniority}",
            f"Stack richiesto: {', '.join(posting.tech_stack[:15]) or 'non specificato'}",
        ]
        if posting.responsibilities:
            lines.append("Responsabilità: " + "; ".join(posting.responsibilities[:6]))
        return "\n".join(lines)

    @staticmethod
    def _apply_ai(review: CvReview, data: dict) -> None:
        try:
            score = int(data.get("overall_score", 0))
        except (TypeError, ValueError):
            score = 0
        review.overall_score = max(0, min(100, score))
        review.summary = str(data.get("summary", ""))[:2000]
        review.strengths = [str(s)[:300] for s in (data.get("strengths") or [])][:10]
        review.weaknesses = [str(s)[:300] for s in (data.get("weaknesses") or [])][:10]
        review.suggestions = [str(s)[:400] for s in (data.get("suggestions") or [])][:12]
        review.tailored_summary = str(data.get("tailored_summary", ""))[:1500]
        review.likely_questions = [
            str(s)[:300] for s in (data.get("likely_questions") or [])
        ][:10]
        rewrites: list[CvBulletRewrite] = []
        for row in data.get("bullet_rewrites") or []:
            if isinstance(row, dict) and row.get("original") and row.get("improved"):
                rewrites.append(
                    CvBulletRewrite(
                        original=str(row["original"])[:500],
                        improved=str(row["improved"])[:500],
                        why=str(row.get("why", ""))[:300],
                    )
                )
        review.bullet_rewrites = rewrites[:10]
        review.ai_generated = True

    @staticmethod
    def _heuristic_review(review: CvReview, cv_text: str, posting: JobPosting | None) -> None:
        """Analisi deterministica: copertura keyword, numeri, verbi d'azione, lunghezza."""
        bullets = extract_bullets(cv_text)
        words = len(cv_text.split())
        has_numbers = [b for b in bullets if re.search(r"\d", b)]
        weak_bullets = [
            b
            for b in bullets
            if not set(tokenize(b)) & ACTION_VERBS and not re.search(r"\d", b)
        ]

        total_keywords = len(review.matched_keywords) + len(review.missing_keywords)
        coverage = (
            round(len(review.matched_keywords) / total_keywords * 100) if total_keywords else 50
        )
        quantified = round(len(has_numbers) / len(bullets) * 100) if bullets else 0
        review.overall_score = max(0, min(100, round(coverage * 0.6 + quantified * 0.4)))

        review.summary = (
            f"Analisi automatica (AI non configurata). Il CV contiene circa {words} parole e "
            f"{len(bullets)} voci elenco. Copertura delle parole chiave dell'annuncio: "
            f"{coverage}%. Voci con un dato numerico: {quantified}%."
        )

        strengths: list[str] = []
        if review.matched_keywords:
            strengths.append(
                "Tecnologie dell'annuncio già presenti nel CV: "
                + ", ".join(review.matched_keywords[:12])
            )
        if quantified >= 40:
            strengths.append("Buona parte delle voci riporta un risultato quantificato.")
        review.strengths = strengths or ["Nessun punto di forza rilevabile automaticamente."]

        weaknesses: list[str] = []
        if review.missing_keywords:
            weaknesses.append(
                "Parole chiave dell'annuncio assenti dal CV: "
                + ", ".join(review.missing_keywords[:12])
            )
        if quantified < 40:
            weaknesses.append(
                f"Solo il {quantified}% delle voci contiene un numero: i risultati misurabili "
                "sono ciò che distingue un CV."
            )
        if weak_bullets:
            weaknesses.append(
                f"{len(weak_bullets)} voci non iniziano con un verbo d'azione né riportano "
                "un risultato."
            )
        if words > 900:
            weaknesses.append(
                f"Il CV è lungo (~{words} parole): per un profilo tecnico una pagina, "
                "due al massimo, è lo standard."
            )
        review.weaknesses = weaknesses

        suggestions = [
            "Riscrivi le voci nella forma: verbo d'azione + cosa hai fatto + risultato misurabile.",
            "Metti in cima le tecnologie che l'annuncio cita come indispensabili.",
        ]
        if review.missing_keywords:
            suggestions.insert(
                0,
                "Se hai davvero esperienza su "
                + ", ".join(review.missing_keywords[:5])
                + ", rendila esplicita: i filtri ATS cercano le parole letterali.",
            )
        if posting and posting.seniority in {"senior", "staff"}:
            suggestions.append(
                "Per una posizione senior aggiungi l'impatto delle scelte tecniche, "
                "non solo le tecnologie usate."
            )
        review.suggestions = suggestions
        review.likely_questions = [
            f"Raccontami come hai usato {kw} in un progetto reale."
            for kw in review.matched_keywords[:5]
        ]
        review.bullet_rewrites = [
            CvBulletRewrite(
                original=bullet,
                improved="[aggiungi un verbo d'azione iniziale e un risultato misurabile]",
                why="La voce non comunica né l'azione né l'esito.",
            )
            for bullet in weak_bullets[:5]
        ]
