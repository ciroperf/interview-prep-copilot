"""Caricamento e interrogazione della knowledge base (file YAML in app/content)."""

from __future__ import annotations

import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml

from ..domain.models import CodingProblem, KnowledgePack, QuizQuestion, Topic

logger = logging.getLogger(__name__)

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

# Parole troppo comuni per essere indicative in una ricerca.
STOPWORDS = {
    "di", "del", "della", "dei", "delle", "il", "lo", "la", "i", "gli", "le", "un", "uno",
    "una", "e", "ed", "o", "con", "per", "su", "in", "da", "che", "come", "cosa", "quando",
    "the", "a", "an", "of", "to", "and", "or", "for", "with", "on", "is", "are",
    "we", "you", "our", "your", "at", "as", "by", "be", "it", "this", "that", "from",
}

# Ponte fra il gergo degli annunci di lavoro e gli argomenti del catalogo.
# Serve a "circoscrivere" i contenuti: da una parola dell'annuncio ai temi da studiare.
TERM_HINTS: dict[str, list[str]] = {
    "rest": ["core-02-rest-vs-graphql", "core-03-http-methods", "core-04-http-status-codes"],
    "api": ["core-01-what-is-an-api", "core-03-http-methods", "core-04-http-status-codes"],
    "graphql": ["core-02-rest-vs-graphql"],
    "grpc": ["dist-29-service-communication"],
    "oauth": ["core-08-oauth2", "core-07-sessions-vs-jwt"],
    "jwt": ["core-07-sessions-vs-jwt", "core-06-authn-vs-authz"],
    "auth": ["core-06-authn-vs-authz", "core-07-sessions-vs-jwt", "core-08-oauth2"],
    "sicurezza": ["eng-04-security", "core-06-authn-vs-authz"],
    "security": ["eng-04-security", "core-06-authn-vs-authz"],
    "owasp": ["eng-04-security"],
    "sql": ["db-11-sql-vs-nosql", "db-12-indexes", "db-14-transactions-isolation"],
    "postgres": ["db-12-indexes", "db-14-transactions-isolation", "db-13-acid"],
    "postgresql": ["db-12-indexes", "db-14-transactions-isolation", "db-13-acid"],
    "mysql": ["db-12-indexes", "db-14-transactions-isolation"],
    "database": ["db-11-sql-vs-nosql", "db-12-indexes", "db-13-acid"],
    "nosql": ["db-11-sql-vs-nosql", "db-17-sharding-partitioning"],
    "mongodb": ["db-11-sql-vs-nosql", "db-15-normalization"],
    "dynamodb": ["db-11-sql-vs-nosql", "db-17-sharding-partitioning"],
    "cosmos": ["db-11-sql-vs-nosql", "db-17-sharding-partitioning"],
    "redis": ["cache-21-what-and-where", "cache-22-eviction", "rel-34-distributed-locking"],
    "cache": ["cache-21-what-and-where", "cache-23-consistency", "cache-22-eviction"],
    "caching": ["cache-21-what-and-where", "cache-23-consistency"],
    "cdn": ["cache-24-cdn"],
    "kafka": ["dist-30-message-queues", "rel-35-event-driven", "rel-31-delivery-semantics"],
    "rabbitmq": ["dist-30-message-queues", "dist-29-service-communication"],
    "sqs": ["dist-30-message-queues"],
    "servicebus": ["dist-30-message-queues"],
    "code": ["dist-30-message-queues"],
    "eventi": ["rel-35-event-driven", "dist-30-message-queues"],
    "event": ["rel-35-event-driven"],
    "microservizi": [
        "dist-28-microservices-monolith",
        "dist-29-service-communication",
        "rel-36-saga",
    ],
    "microservices": [
        "dist-28-microservices-monolith",
        "dist-29-service-communication",
        "rel-36-saga",
    ],
    "monolite": ["dist-28-microservices-monolith"],
    "scalabilita": [
        "dist-27-horizontal-vertical",
        "dist-26-load-balancing",
        "rel-40-traffic-spikes",
    ],
    "scalability": ["dist-27-horizontal-vertical", "rel-40-traffic-spikes"],
    "distribuiti": ["dist-28-microservices-monolith", "rel-31-delivery-semantics"],
    "architettura": ["sd-01-interview-framework", "dist-28-microservices-monolith"],
    "architecture": ["sd-01-interview-framework", "dist-28-microservices-monolith"],
    "system": ["sd-01-interview-framework", "sd-02-classic-designs"],
    "performance": ["db-12-indexes", "cache-21-what-and-where", "rel-40-traffic-spikes"],
    "latenza": ["rel-38-observability", "cache-24-cdn"],
    "monitoring": ["rel-38-observability"],
    "observability": ["rel-38-observability"],
    "prometheus": ["rel-38-observability"],
    "grafana": ["rel-38-observability"],
    "opentelemetry": ["rel-38-observability"],
    "sre": [
        "rel-38-observability",
        "rel-37-graceful-degradation",
        "rel-32-retries-timeouts-breakers",
    ],
    "resilienza": ["rel-32-retries-timeouts-breakers", "rel-37-graceful-degradation"],
    "affidabilita": ["rel-32-retries-timeouts-breakers", "rel-37-graceful-degradation"],
    "docker": ["eng-03-cloud-basics"],
    "container": ["eng-03-cloud-basics"],
    "kubernetes": ["eng-03-cloud-basics", "rel-39-deployments"],
    "k8s": ["eng-03-cloud-basics", "rel-39-deployments"],
    "terraform": ["eng-03-cloud-basics"],
    "aws": ["eng-03-cloud-basics"],
    "azure": ["eng-03-cloud-basics"],
    "gcp": ["eng-03-cloud-basics"],
    "cloud": ["eng-03-cloud-basics", "dist-27-horizontal-vertical"],
    "devops": ["eng-03-cloud-basics", "rel-39-deployments"],
    "cicd": ["rel-39-deployments", "eng-01-testing"],
    "deploy": ["rel-39-deployments"],
    "git": ["eng-02-git"],
    "test": ["eng-01-testing"],
    "testing": ["eng-01-testing"],
    "pytest": ["eng-01-testing", "eng-06-python"],
    "tdd": ["eng-01-testing"],
    "qualita": ["eng-05-code-quality", "eng-01-testing"],
    "code review": ["eng-05-code-quality", "eng-02-git"],
    "pull request": ["eng-02-git", "eng-05-code-quality"],
    "branching": ["eng-02-git"],
    "logging": ["rel-38-observability"],
    "tracing": ["rel-38-observability"],
    "metriche": ["rel-38-observability"],
    "design": ["eng-05-code-quality", "sd-01-interview-framework"],
    "refactoring": ["eng-05-code-quality"],
    "python": ["eng-06-python"],
    "django": ["eng-06-python", "core-01-what-is-an-api"],
    "fastapi": ["eng-06-python", "core-01-what-is-an-api"],
    "flask": ["eng-06-python"],
    "javascript": ["eng-07-javascript"],
    "typescript": ["eng-07-javascript"],
    "node": ["eng-07-javascript", "core-05-stateless-vs-stateful"],
    "nodejs": ["eng-07-javascript"],
    "react": ["fe-01-react-rendering", "fe-02-react-stato-dati", "eng-07-javascript"],
    "hooks": ["fe-01-react-rendering"],
    "redux": ["fe-02-react-stato-dati"],
    "angular": ["fe-03-angular", "eng-07-javascript"],
    "rxjs": ["fe-03-angular", "js-05-async-patterns"],
    "vue": ["fe-01-react-rendering", "eng-07-javascript"],
    "frontend": ["fe-04-css-layout", "fe-01-react-rendering", "eng-07-javascript"],
    "css": ["fe-04-css-layout", "fe-05-web-performance"],
    "sass": ["fe-04-css-layout"],
    "tailwind": ["fe-04-css-layout"],
    "responsive": ["fe-04-css-layout"],
    "html": ["fe-04-css-layout", "fe-05-web-performance"],
    "accessibilita": ["fe-06-testing-componenti", "fe-04-css-layout"],
    "accessibility": ["fe-06-testing-componenti", "fe-04-css-layout"],
    "web vitals": ["fe-05-web-performance"],
    "ux": ["fe-05-web-performance", "fe-04-css-layout"],
    "java": ["java-01-linguaggio-jvm", "java-02-concorrenza", "java-03-spring-core"],
    "jvm": ["java-01-linguaggio-jvm"],
    "spring": ["java-03-spring-core", "java-04-spring-web"],
    "springboot": ["java-03-spring-core", "java-04-spring-web"],
    "hibernate": ["java-05-jpa-transazioni", "db-12-indexes"],
    "jpa": ["java-05-jpa-transazioni"],
    "maven": ["java-06-build-testing"],
    "gradle": ["java-06-build-testing"],
    "junit": ["java-06-build-testing", "eng-01-testing"],
    "kotlin": ["java-01-linguaggio-jvm", "java-03-spring-core"],
    "algoritmi": ["dsa-01-complexity", "dsa-11-dynamic-programming"],
    "algorithms": ["dsa-01-complexity", "dsa-11-dynamic-programming"],
    "dsa": ["dsa-01-complexity", "dsa-03-hash-maps", "dsa-09-graphs"],
    "leetcode": ["dsa-03-hash-maps", "dsa-11-dynamic-programming", "dsa-09-graphs"],
    "coding": ["dsa-01-complexity", "dsa-02-arrays-two-pointers"],
    "concorrenza": ["rel-33-race-conditions", "db-20-locking", "rel-34-distributed-locking"],
    "concurrency": ["rel-33-race-conditions", "db-20-locking"],
    "multithreading": ["rel-33-race-conditions", "eng-06-python"],
    "async": ["dist-29-service-communication", "eng-07-javascript"],
    "pagamenti": ["core-10-idempotency", "rel-36-saga"],
    "payment": ["core-10-idempotency", "rel-36-saga"],
    "fintech": ["core-10-idempotency", "db-14-transactions-isolation", "eng-04-security"],
    "ecommerce": ["rel-36-saga", "rel-40-traffic-spikes", "cache-21-what-and-where"],
    "streaming": ["dist-30-message-queues", "rel-35-event-driven"],
    "etl": ["dist-30-message-queues", "db-11-sql-vs-nosql"],
    "backend": ["core-01-what-is-an-api", "db-12-indexes", "cache-21-what-and-where"],
    # Pattern di strutturazione del codice
    "repository": ["pat-02-repository", "pat-01-layered-architecture"],
    "service": ["pat-03-service-layer", "pat-01-layered-architecture"],
    "dto": ["pat-04-dto-entity-model"],
    "layer": ["pat-01-layered-architecture"],
    "layered": ["pat-01-layered-architecture"],
    "mvc": ["pat-01-layered-architecture"],
    "clean": ["pat-06-hexagonal-clean"],
    "hexagonal": ["pat-06-hexagonal-clean"],
    "esagonale": ["pat-06-hexagonal-clean"],
    "ddd": ["pat-07-ddd-tactical", "pat-06-hexagonal-clean"],
    "aggregate": ["pat-07-ddd-tactical"],
    "dominio": ["pat-07-ddd-tactical", "pat-03-service-layer"],
    "cqrs": ["pat-11-cqrs", "rel-35-event-driven"],
    "pattern": ["pat-09-gof-patterns", "pat-01-layered-architecture"],
    "patterns": ["pat-09-gof-patterns"],
    "gof": ["pat-09-gof-patterns"],
    "strategy": ["pat-09-gof-patterns"],
    "factory": ["pat-09-gof-patterns"],
    "injection": ["pat-05-dependency-injection"],
    "ioc": ["pat-05-dependency-injection"],
    "orm": ["db-12-indexes", "pat-02-repository", "pat-08-unit-of-work"],
    "transazioni": ["db-13-acid", "db-14-transactions-isolation", "pat-08-unit-of-work"],
    "solid": ["eng-05-code-quality", "pat-05-dependency-injection"],
    "manutenibilita": ["pat-10-project-structure", "eng-05-code-quality"],
    "modularita": ["pat-10-project-structure", "dist-28-microservices-monolith"],
    "pulito": ["eng-05-code-quality", "pat-06-hexagonal-clean"],
}


def normalize(text: str) -> str:
    """Minuscolo e senza accenti: rende confrontabili 'scalabilità' e 'scalabilita'."""
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9+#.]{2,}", normalize(text))
    # I punti interni servono per "node.js" ma non vanno tenuti ai bordi.
    cleaned = [t.strip(".") for t in tokens]
    return [t for t in cleaned if t and t not in STOPWORDS]


class KnowledgeBase:
    """Indice in memoria di argomenti, domande e problemi."""

    def __init__(self, content_dir: Path | None = None) -> None:
        self.content_dir = Path(content_dir or CONTENT_DIR)
        self.topics: dict[str, Topic] = {}
        self.questions: dict[str, QuizQuestion] = {}
        self.problems: dict[str, CodingProblem] = {}
        self.questions_by_topic: dict[str, list[str]] = {}
        self.problems_by_topic: dict[str, list[str]] = {}
        # I percorsi sui macroargomenti: un linguaggio o il cloud non stanno in
        # una scheda sola, e un elenco ordinato vale più di un riassunto lungo.
        self.packs: dict[str, KnowledgePack] = {}
        self._topic_tokens: dict[str, set[str]] = {}
        # TERM_HINTS è scritto a mano per i contenuti del repository; qui si
        # accumulano i collegamenti degli argomenti aggiunti a partire dagli annunci.
        self._dynamic_hints: dict[str, list[str]] = {}
        self._load()

    # --- caricamento --------------------------------------------------------

    def _read_all(self, pattern: str) -> list[dict]:
        rows: list[dict] = []
        for path in sorted(self.content_dir.glob(pattern)):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            if not isinstance(data, list):
                raise ValueError(f"{path.name}: attesa una lista di elementi")
            rows.extend(data)
        return rows

    def _load(self) -> None:
        for row in self._read_all("topics_*.yaml"):
            topic = Topic(**row)
            if topic.id in self.topics:
                raise ValueError(f"Argomento duplicato: {topic.id}")
            self.topics[topic.id] = topic

        for row in self._read_all("questions_*.yaml"):
            question = QuizQuestion(**row)
            if question.topic_id not in self.topics:
                raise ValueError(f"{question.id}: topic_id sconosciuto {question.topic_id}")
            self.questions[question.id] = question
            self.questions_by_topic.setdefault(question.topic_id, []).append(question.id)

        for row in self._read_all("problems.yaml"):
            problem = CodingProblem(**row)
            self.problems[problem.id] = problem
            for topic_id in problem.topic_ids:
                if topic_id not in self.topics:
                    raise ValueError(f"{problem.id}: topic_id sconosciuto {topic_id}")
                self.problems_by_topic.setdefault(topic_id, []).append(problem.id)

        for row in self._read_all("packs.yaml"):
            pack = KnowledgePack(**row)
            sconosciuti = [t for t in pack.topic_ids if t not in self.topics]
            if sconosciuti:
                raise ValueError(f"{pack.id}: argomenti sconosciuti {sconosciuti}")
            self.packs[pack.id] = pack

        for topic in self.topics.values():
            self._index_topic(topic)

        logger.info(
            "Knowledge base: %d argomenti, %d domande, %d problemi, %d percorsi",
            len(self.topics),
            len(self.questions),
            len(self.problems),
            len(self.packs),
        )

    def _index_topic(self, topic: Topic) -> None:
        """Calcola i token su cui si basa lo scoring di pertinenza."""
        blob = " ".join(
            [topic.title, topic.category, " ".join(topic.tags), topic.summary]
            + topic.key_points
        )
        self._topic_tokens[topic.id] = set(tokenize(blob))

    # --- interrogazione -----------------------------------------------------

    @property
    def categories(self) -> list[str]:
        return sorted({t.category for t in self.topics.values()})

    def list_topics(
        self,
        category: str | None = None,
        track: str | None = None,
        query: str | None = None,
    ) -> list[Topic]:
        items = list(self.topics.values())
        if category:
            items = [t for t in items if t.category == category]
        if track:
            items = [t for t in items if t.track == track]
        if query:
            wanted = set(tokenize(query))
            items = [t for t in items if wanted & self._topic_tokens[t.id]]
        return sorted(items, key=lambda t: (t.category, t.id))

    def score_topics(self, terms: list[str]) -> dict[str, float]:
        """Assegna a ogni argomento un punteggio di pertinenza rispetto ai termini dati.

        I termini arrivano dall'annuncio (stack, requisiti, focus del colloquio).
        Il punteggio combina i suggerimenti espliciti di TERM_HINTS con la
        sovrapposizione di token, che copre i casi non mappati a mano.
        """
        scores: dict[str, float] = {}
        for raw_term in terms:
            tokens = tokenize(raw_term)
            if not tokens:
                continue
            # Peso: i termini brevi e specifici (una parola) sono i piu' affidabili.
            weight = 1.0 if len(tokens) == 1 else 0.7

            # La frase intera prima dei singoli token: le chiavi a piu' parole di
            # TERM_HINTS - "code review", "pull request" - altrimenti non scattano
            # mai, perche' la ricerca avverrebbe solo token per token.
            frase = " ".join(tokens)
            if len(tokens) > 1:
                for topic_id in TERM_HINTS.get(frase, []):
                    if topic_id in self.topics:
                        scores[topic_id] = scores.get(topic_id, 0.0) + 4.0

            for token in tokens:
                for topic_id in TERM_HINTS.get(token, []):
                    if topic_id in self.topics:
                        scores[topic_id] = scores.get(topic_id, 0.0) + 3.0 * weight
                # Un argomento creato apposta per questo termine deve vincere su
                # uno generico che lo cita di sfuggita: pesa di più.
                for topic_id in self._dynamic_hints.get(token, []):
                    if topic_id in self.topics:
                        scores[topic_id] = scores.get(topic_id, 0.0) + 4.0 * weight

            token_set = set(tokens)
            for topic_id, topic_tokens in self._topic_tokens.items():
                overlap = len(token_set & topic_tokens)
                if overlap:
                    topic = self.topics[topic_id]
                    boost = 1.5 if token_set & set(tokenize(topic.title)) else 1.0
                    scores[topic_id] = scores.get(topic_id, 0.0) + overlap * boost * weight
        return scores

    # --- ampliamento a runtime ---------------------------------------------

    def register_topic(self, topic: Topic, questions: list[QuizQuestion]) -> None:
        """Inserisce un argomento nell'indice in memoria.

        Usata sia al riavvio, per ricaricare gli argomenti persistiti, sia subito
        dopo averne creato uno nuovo: da quel momento piano, quiz e ricerca lo
        vedono come qualunque altro argomento.
        """
        self.topics[topic.id] = topic
        self.questions_by_topic.setdefault(topic.id, [])
        for question in questions:
            if question.topic_id != topic.id:
                raise ValueError(f"{question.id}: topic_id non corrisponde a {topic.id}")
            self.questions[question.id] = question
            if question.id not in self.questions_by_topic[topic.id]:
                self.questions_by_topic[topic.id].append(question.id)
        self._index_topic(topic)
        self._index_hints(topic)

    def _index_hints(self, topic: Topic) -> None:
        """Collega il termine che ha generato l'argomento all'argomento stesso.

        Senza questo, aggiungere "Kubernetes" al catalogo non basterebbe: lo
        scoring continuerebbe a preferire un argomento generico già presente.
        """
        terms = [topic.source_term, topic.title, *topic.tags]
        for term in terms:
            for token in tokenize(term):
                bucket = self._dynamic_hints.setdefault(token, [])
                if topic.id not in bucket:
                    bucket.append(topic.id)

    def remove_topic(self, topic_id: str) -> bool:
        """Rimuove un argomento aggiunto a runtime. Quelli del repository restano."""
        topic = self.topics.get(topic_id)
        if topic is None or not topic.custom:
            return False
        for question_id in self.questions_by_topic.pop(topic_id, []):
            self.questions.pop(question_id, None)
        self.problems_by_topic.pop(topic_id, None)
        self._topic_tokens.pop(topic_id, None)
        for bucket in self._dynamic_hints.values():
            if topic_id in bucket:
                bucket.remove(topic_id)
        del self.topics[topic_id]
        return True

    def load_custom(self, rows: list[dict]) -> int:
        """Ricarica gli argomenti persistiti nello storage. Restituisce quanti ne ha caricati."""
        loaded = 0
        for row in rows:
            try:
                topic = Topic(**row["topic"])
                questions = [QuizQuestion(**q) for q in row.get("questions", [])]
                self.register_topic(topic, questions)
                loaded += 1
            except Exception as exc:
                logger.warning("Argomento personalizzato non caricabile: %s", exc)
        if loaded:
            logger.info("Caricati %d argomenti aggiunti dagli annunci", loaded)
        return loaded

    def custom_topics(self) -> list[Topic]:
        return sorted(
            (t for t in self.topics.values() if t.custom), key=lambda t: t.title.lower()
        )

    def slugify(self, term: str) -> str:
        """Id stabile e leggibile a partire dal termine dell'annuncio."""
        base = re.sub(r"[^a-z0-9]+", "-", normalize(term)).strip("-") or "argomento"
        candidate = f"custom-{base}"[:60]
        if candidate not in self.topics:
            return candidate
        # Collisione: l'utente sta aggiungendo un termine già presente.
        index = 2
        while f"{candidate}-{index}" in self.topics:
            index += 1
        return f"{candidate}-{index}"

    def questions_for(self, topic_ids: list[str]) -> list[QuizQuestion]:
        out: list[QuizQuestion] = []
        for topic_id in topic_ids:
            for question_id in self.questions_by_topic.get(topic_id, []):
                out.append(self.questions[question_id])
        return out

    def problems_for(self, topic_ids: list[str]) -> list[CodingProblem]:
        seen: set[str] = set()
        out: list[CodingProblem] = []
        for topic_id in topic_ids:
            for problem_id in self.problems_by_topic.get(topic_id, []):
                if problem_id not in seen:
                    seen.add(problem_id)
                    out.append(self.problems[problem_id])
        return out

    def coverage(self, term: str) -> tuple[float, str, bool]:
        """Quanto il catalogo copre un termine: punteggio, argomento migliore, dedicato.

        La distinzione che conta è fra un argomento che parla *di* quel termine e
        uno che lo cita di sfuggita: "Kafka" ha un argomento dedicato, "Kubernetes"
        oggi compare solo dentro un argomento generico sul cloud. Il secondo caso è
        una lacuna da colmare, non una copertura.
        """
        scores = self.score_topics([term])
        if not scores:
            return 0.0, "", False
        topic_id, score = max(scores.items(), key=lambda kv: kv[1])
        wanted = set(tokenize(term))
        if not wanted:
            return score, topic_id, False
        title_tokens = set(tokenize(self.topics[topic_id].title))
        # Metà dei token nel titolo basta: "Repository pattern" è coperto da un
        # argomento che si chiama "...controller, service, repository".
        dedicated = len(wanted & title_tokens) / len(wanted) >= 0.5
        return score, topic_id, dedicated

    def catalog_for_prompt(self, topic_ids: list[str] | None = None, max_items: int = 80) -> str:
        """Catalogo compatto da passare al modello: un argomento per riga."""
        items = [self.topics[i] for i in topic_ids if i in self.topics] if topic_ids else list(
            self.topics.values()
        )
        lines = []
        for topic in items[:max_items]:
            tags = ",".join(topic.tags[:4])
            lines.append(
                f"- {topic.id} | {topic.title} | cat:{topic.category} | "
                f"track:{topic.track} | {topic.estimated_minutes}min | tag:{tags}"
            )
        return "\n".join(lines)


@lru_cache
def get_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase()
