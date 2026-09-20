"""Prompt e schemi JSON usati per le chiamate al modello.

Tenuti tutti qui cosi' si possono rivedere e versionare senza toccare i servizi.
"""

from __future__ import annotations

PERSONA = (
    "Sei un coach tecnico che prepara sviluppatori software ai colloqui. "
    "Hai condotto centinaia di colloqui come hiring manager in aziende di prodotto. "
    "Rispondi in italiano, tenendo i termini tecnici in inglese. "
    "Sii concreto e specifico: niente frasi generiche da manuale."
)

# ---------------------------------------------------------------------------
# Analisi dell'annuncio di lavoro
# ---------------------------------------------------------------------------

JOB_ANALYSIS_SYSTEM = (
    PERSONA
    + " Il tuo compito e' estrarre informazioni strutturate da un annuncio di lavoro. "
    "Estrai solo cio' che e' realmente presente nel testo; non inventare tecnologie. "
    "Se un campo non e' deducibile, lascialo vuoto."
)

JOB_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "role_title": {"type": "string"},
        "seniority": {
            "type": "string",
            "enum": ["intern", "junior", "mid", "senior", "staff", "unknown"],
        },
        "location": {"type": "string"},
        "work_mode": {"type": "string", "description": "remoto, ibrido, on-site"},
        "tech_stack": {"type": "array", "items": {"type": "string"}},
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {
                        "type": "string",
                        "description": "linguaggio, framework, database, cloud, "
                        "architettura, testing, soft-skill, altro",
                    },
                    "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                    "evidence": {
                        "type": "string",
                        "description": "breve citazione dall'annuncio",
                    },
                },
                "required": ["name", "importance"],
            },
        },
        "nice_to_have": {"type": "array", "items": {"type": "string"}},
        "responsibilities": {"type": "array", "items": {"type": "string"}},
        "interview_focus": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Su cosa verte con ogni probabilita' il colloquio tecnico",
        },
        "red_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Segnali di allarme o ambiguita' nell'annuncio",
        },
    },
    "required": ["role_title", "seniority", "tech_stack", "requirements"],
}


def job_analysis_user(raw_text: str, notes: str = "") -> str:
    extra = f"\n\nNote aggiuntive dal candidato:\n{notes}" if notes else ""
    return (
        "Analizza questo annuncio di lavoro e restituisci JSON conforme allo schema.\n\n"
        "Per `importance` usa 5 per cio' che l'annuncio indica come indispensabile "
        "e 1 per cio' che e' solo gradito.\n\n"
        f"--- ANNUNCIO ---\n{raw_text.strip()}\n--- FINE ANNUNCIO ---{extra}"
    )


# ---------------------------------------------------------------------------
# Ricerca sull'azienda
# ---------------------------------------------------------------------------

COMPANY_SYSTEM = (
    PERSONA
    + " Prepari la parte 'conoscitiva' del colloquio: cosa fa l'azienda, come lavora, "
    "che domande fare. Distingui sempre cio' che deduci dall'annuncio da cio' che "
    "ricordi dall'addestramento, e non inventare fatti verificabili come fatturati, "
    "numero di dipendenti o round di finanziamento se non ne sei certo."
)

COMPANY_SCHEMA = {
    "type": "object",
    "properties": {
        "industry": {"type": "string"},
        "size": {"type": "string"},
        "products": {"type": "array", "items": {"type": "string"}},
        "tech_culture": {"type": "string"},
        "interview_process": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Fasi tipiche del processo di selezione per questo tipo di azienda",
        },
        "talking_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Punti da citare per dimostrare interesse informato",
        },
        "questions_to_ask": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Domande intelligenti da fare all'intervistatore",
        },
        "research_notes": {
            "type": "string",
            "description": "Cosa il candidato dovrebbe verificare da solo prima del colloquio",
        },
    },
    "required": ["talking_points", "questions_to_ask"],
}


def company_user(company_name: str, role_title: str, job_excerpt: str) -> str:
    return (
        f"Azienda: {company_name or 'non indicata'}\n"
        f"Ruolo: {role_title or 'non indicato'}\n\n"
        "Estratto dell'annuncio:\n"
        f"{job_excerpt[:4000]}\n\n"
        "Prepara la scheda azienda. Se non conosci questa azienda specifica, dillo "
        "esplicitamente in `research_notes` e basa il resto su cio' che si deduce "
        "dall'annuncio e sul settore di appartenenza."
    )


# ---------------------------------------------------------------------------
# Piano di studi
# ---------------------------------------------------------------------------

PLAN_SYSTEM = (
    PERSONA
    + " Costruisci piani di studio realistici. Il tempo e' la risorsa scarsa: "
    "meglio pochi argomenti padroneggiati che venti sfiorati. "
    "Dai priorita' a cio' che l'annuncio rende probabile in sede di colloquio."
)

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {
            "type": "string",
            "description": "2-4 frasi sulla strategia di preparazione",
        },
        "focus_areas": {"type": "array", "items": {"type": "string"}},
        "gap_analysis": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lacune probabili tra il profilo e la posizione",
        },
        "selected_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic_id": {
                        "type": "string",
                        "description": "id esatto preso dal catalogo fornito",
                    },
                    "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                    "rationale": {
                        "type": "string",
                        "description": "perche' serve per QUESTO colloquio, in una frase",
                    },
                },
                "required": ["topic_id", "priority"],
            },
        },
        "extra_recommendations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Temi importanti per questo ruolo ma assenti dal catalogo",
        },
    },
    "required": ["summary", "focus_areas", "selected_topics"],
}


def plan_user(
    job_summary: str,
    catalog: str,
    days: int,
    daily_minutes: int,
    known_strengths: list[str],
    weak_areas: list[str],
) -> str:
    strengths = ", ".join(known_strengths) if known_strengths else "non dichiarati"
    weaknesses = ", ".join(weak_areas) if weak_areas else "non dichiarate"
    budget = days * daily_minutes
    return (
        f"POSIZIONE\n{job_summary}\n\n"
        f"TEMPO A DISPOSIZIONE: {days} giorni x {daily_minutes} minuti = {budget} minuti totali\n"
        f"PUNTI DI FORZA dichiarati: {strengths}\n"
        f"AREE DEBOLI dichiarate: {weaknesses}\n\n"
        "CATALOGO ARGOMENTI DISPONIBILI (usa esclusivamente questi id):\n"
        f"{catalog}\n\n"
        "Seleziona gli argomenti che stanno nel budget di tempo, ordinali per priorita' "
        "(5 = imprescindibile per questo colloquio) e motiva ogni scelta collegandola "
        "all'annuncio. Abbassa la priorita' dei punti di forza gia' dichiarati e alzala "
        "per le aree deboli che l'annuncio richiede. Non inventare id non presenti nel "
        "catalogo: cio' che manca va in `extra_recommendations`."
    )


# ---------------------------------------------------------------------------
# Generazione domande a risposta multipla
# ---------------------------------------------------------------------------

QUIZ_SYSTEM = (
    PERSONA
    + " Scrivi domande a risposta multipla da colloquio tecnico. "
    "Ogni domanda ha esattamente 4 opzioni e una sola risposta corretta. "
    "I distrattori devono essere plausibili: niente opzioni palesemente assurde. "
    "Evita domande mnemoniche, preferisci quelle che verificano la comprensione."
)

QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic_id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "answer_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                },
                "required": ["topic_id", "prompt", "options", "answer_index", "explanation"],
            },
        }
    },
    "required": ["questions"],
}


def quiz_user(topics_block: str, count: int, role_context: str, difficulty: str | None) -> str:
    level = f"Difficolta' richiesta: {difficulty}.\n" if difficulty else ""
    return (
        f"Contesto del colloquio: {role_context}\n\n"
        f"{level}"
        f"Genera {count} domande a risposta multipla sugli argomenti seguenti, "
        "distribuendole in modo equilibrato. Usa gli id esatti nel campo `topic_id`.\n\n"
        f"{topics_block}"
    )


# ---------------------------------------------------------------------------
# Revisione del codice
# ---------------------------------------------------------------------------

CODE_REVIEW_SYSTEM = (
    PERSONA
    + " Rivedi la soluzione come faresti in un colloquio dal vivo: correttezza "
    "prima di tutto, poi complessita', poi leggibilita'. Indica i casi limite non "
    "gestiti con un controesempio concreto. Non riscrivere l'intera soluzione: "
    "guida il candidato a trovarla."
)

CODE_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "description": "Giudizio sintetico in una frase, come lo daresti a fine colloquio",
        },
        "correctness": {
            "type": "string",
            "description": "La soluzione e' corretta? Se no, con quale input fallisce",
        },
        "complexity": {"type": "string", "description": "Complessita' di tempo e spazio stimata"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "interview_notes": {
            "type": "string",
            "description": "Cosa direbbe un intervistatore di questa soluzione",
        },
    },
    "required": ["verdict", "correctness", "complexity", "improvements"],
}


def code_review_user(problem: str, code: str, execution_report: str = "") -> str:
    report = f"\n\nESITO DEI TEST AUTOMATICI:\n{execution_report}" if execution_report else ""
    return (
        f"PROBLEMA\n{problem}\n\n"
        f"SOLUZIONE PROPOSTA (Python)\n```python\n{code}\n```{report}\n\n"
        "Valuta la soluzione."
    )


# ---------------------------------------------------------------------------
# Revisione del CV
# ---------------------------------------------------------------------------

CV_SYSTEM = (
    PERSONA
    + " Rivedi il CV nell'ottica di QUESTA specifica posizione. "
    "Sii schietto: un CV mediocre che riceve complimenti non aiuta nessuno. "
    "Lavora solo sul contenuto presente: non inventare esperienze, aziende o numeri "
    "che il candidato non ha scritto. Dove un dato quantitativo servirebbe, indica "
    "al candidato di aggiungerlo con un segnaposto esplicito."
)

CV_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "description": "Quanto il CV e' allineato a questa posizione",
        },
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Azioni concrete, ordinate per impatto",
        },
        "bullet_rewrites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "improved": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["original", "improved"],
            },
            "description": "Riscritture di bullet realmente presenti nel CV",
        },
        "tailored_summary": {
            "type": "string",
            "description": "Proposta di sezione 'Profilo' calibrata sull'annuncio",
        },
        "likely_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Domande che il CV stesso provoca in sede di colloquio",
        },
    },
    "required": ["overall_score", "summary", "strengths", "weaknesses", "suggestions"],
}


def cv_user(cv_text: str, job_summary: str, missing_keywords: list[str]) -> str:
    gap = ", ".join(missing_keywords[:25]) if missing_keywords else "nessuna rilevata"
    return (
        f"POSIZIONE TARGET\n{job_summary}\n\n"
        f"PAROLE CHIAVE DELL'ANNUNCIO ASSENTI DAL CV (analisi automatica): {gap}\n\n"
        f"--- CV ---\n{cv_text[:18000]}\n--- FINE CV ---\n\n"
        "Valuta il CV rispetto alla posizione e proponi miglioramenti concreti."
    )


# ---------------------------------------------------------------------------
# Ampliamento della knowledge base
# ---------------------------------------------------------------------------

TOPIC_SYSTEM = (
    PERSONA
    + " Scrivi una scheda di studio su un argomento tecnico, pensata per chi deve "
    "affrontare un colloquio fra pochi giorni. Niente storia della tecnologia e "
    "niente elenchi di comandi: servono i concetti che un intervistatore verifica "
    "davvero e la risposta da dare a voce. Se l'argomento è un prodotto specifico "
    "(un database, un orchestratore, un broker), concentrati sul modello mentale e "
    "sui trade-off, non sulla sintassi."
)

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Titolo della scheda, conciso"},
        "category": {
            "type": "string",
            "description": "Una fra: core-concepts, databases, caching, distributed, "
            "reliability, dsa, system-design, patterns, engineering, languages",
        },
        "track": {
            "type": "string",
            "enum": ["knowledge", "technical"],
            "description": "knowledge se si studia e si racconta, technical se si esercita",
        },
        "level": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "summary": {
            "type": "string",
            "description": "2-4 frasi: cos'è e quale problema risolve",
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "6-10 punti che un intervistatore si aspetta di sentire",
        },
        "interview_answer": {
            "type": "string",
            "description": "La risposta da dare a voce, in prima persona, 4-8 frasi",
        },
        "pitfalls": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Errori tipici e risposte che fanno cattiva impressione",
        },
        "follow_up_questions": {"type": "array", "items": {"type": "string"}},
        "estimated_minutes": {"type": "integer", "minimum": 10, "maximum": 120},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "answer_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                },
                "required": ["prompt", "options", "answer_index", "explanation"],
            },
        },
    },
    "required": ["title", "summary", "key_points", "interview_answer"],
}


def topic_user(term: str, role_context: str, num_questions: int) -> str:
    quiz_part = (
        f"Aggiungi {num_questions} domande a risposta multipla con 4 opzioni e una sola "
        "risposta corretta, con distrattori plausibili."
        if num_questions
        else "Non servono domande a risposta multipla."
    )
    return (
        f"ARGOMENTO DA PREPARARE: {term}\n\n"
        f"CONTESTO DEL COLLOQUIO: {role_context}\n\n"
        "Scrivi la scheda di studio. Calibra la profondità sul contesto: per un ruolo "
        "junior servono i fondamenti, per un senior i trade-off e i casi limite. "
        f"{quiz_part}"
    )
