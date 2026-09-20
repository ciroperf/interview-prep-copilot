"""Percorso completo attraverso l'API, come lo usa il frontend."""

from __future__ import annotations

import io

from conftest import SAMPLE_JOB


def test_health_e_meta(client):
    assert client.get("/api/health").json() == {"status": "ok"}

    meta = client.get("/api/meta").json()
    assert meta["ai_enabled"] is False
    assert meta["content"]["topics"] >= 60
    assert "core-concepts" in meta["content"]["categories"]


def test_knowledge_base_navigabile(client):
    categories = client.get("/api/knowledge/categories").json()["categories"]
    assert any(c["id"] == "reliability" and c["count"] == 10 for c in categories)

    topics = client.get("/api/knowledge/topics", params={"category": "caching"}).json()
    assert topics["total"] == 5

    detail = client.get("/api/knowledge/topics/core-10-idempotency").json()
    assert "idempotency key" in detail["topic"]["interview_answer"].lower()

    assert client.get("/api/knowledge/topics/non-esiste").status_code == 404


def test_ricerca_testuale_sugli_argomenti(client):
    found = client.get("/api/knowledge/topics", params={"q": "kafka"}).json()
    assert found["total"] >= 1
    assert any("kafka" in t["title"].lower() for t in found["topics"])


def test_flusso_completo_annuncio_piano_quiz(client):
    # 1. Analisi dell'annuncio
    created = client.post(
        "/api/jobs",
        json={"raw_text": SAMPLE_JOB, "company_name": "Acme Pay", "research_company": False},
    )
    assert created.status_code == 201
    job = created.json()["job"]
    assert job["seniority"] == "senior"
    assert "Kafka" in job["tech_stack"]

    assert client.get("/api/jobs").json()["total"] == 1
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200

    # 2. Piano di studi
    plan_response = client.post(
        "/api/plans",
        json={"job_id": job["id"], "days": 7, "daily_minutes": 90, "use_ai": False},
    )
    assert plan_response.status_code == 201
    payload = plan_response.json()
    plan = payload["plan"]
    assert plan["items"]
    assert payload["progress"]["percent"] == 0
    assert payload["by_track"]["knowledge"]["total"] > 0
    assert payload["by_track"]["technical"]["total"] > 0
    assert len(payload["by_day"]) <= 7

    # 3. Avanzamento su un'attività
    item_id = plan["items"][0]["id"]
    updated = client.patch(
        f"/api/plans/{plan['id']}/items/{item_id}", json={"status": "done"}
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["status"] == "done"
    assert updated.json()["progress"]["done"] == 1

    # Lo stato è persistito
    reloaded = client.get(f"/api/plans/{plan['id']}").json()
    assert reloaded["progress"]["done"] == 1

    # 4. Quiz mirato sull'annuncio
    quiz = client.post(
        "/api/quizzes", json={"job_id": job["id"], "num_questions": 5, "use_ai": False}
    )
    assert quiz.status_code == 201
    quiz_data = quiz.json()
    assert len(quiz_data["questions"]) == 5
    # Le soluzioni non devono uscire dal server prima della consegna.
    assert all("answer_index" not in q for q in quiz_data["questions"])

    # 5. Consegna
    answers = [{"question_id": q["id"], "selected_index": 0} for q in quiz_data["questions"]]
    result = client.post(f"/api/quizzes/{quiz_data['id']}/submit", json={"answers": answers})
    assert result.status_code == 200
    body = result.json()
    assert body["total"] == 5
    assert 0 <= body["score"] <= 100
    assert all("answer_index" in a for a in body["answers"])

    # Doppia consegna rifiutata
    assert client.post(
        f"/api/quizzes/{quiz_data['id']}/submit", json={"answers": answers}
    ).status_code == 409


def test_piano_su_annuncio_inesistente(client):
    response = client.post(
        "/api/plans", json={"job_id": "job_inesistente", "days": 5, "daily_minutes": 60}
    )
    assert response.status_code == 404


def test_annuncio_troppo_corto_rifiutato(client):
    assert client.post("/api/jobs", json={"raw_text": "corto"}).status_code == 422


def test_problemi_di_coding(client):
    listing = client.get("/api/problems").json()
    assert listing["total"] >= 10

    detail = client.get("/api/problems/p-two-sum").json()["problem"]
    assert "solution" not in detail
    assert detail["function_name"] == "two_sum"
    assert all(not t["hidden"] for t in detail["tests"])

    review = client.post(
        "/api/problems/p-two-sum/submit",
        json={"problem_id": "p-two-sum", "code": "def two_sum(nums, target): return []"},
    )
    assert review.status_code == 201 or review.status_code == 200
    body = review.json()["review"]
    assert body["problem_id"] == "p-two-sum"
    assert body["improvements"], "senza AI devono comunque arrivare gli hint"

    # La soluzione di riferimento sta su una rotta separata.
    assert "def two_sum" in client.get("/api/problems/p-two-sum/solution").json()["solution"]


def test_problemi_filtrati_per_annuncio(client):
    job = client.post(
        "/api/jobs", json={"raw_text": SAMPLE_JOB, "research_company": False}
    ).json()["job"]
    listing = client.get("/api/problems", params={"job_id": job["id"], "limit": 5}).json()
    assert 0 < listing["total"] <= 5


def test_revisione_cv(client):
    job = client.post(
        "/api/jobs", json={"raw_text": SAMPLE_JOB, "research_company": False}
    ).json()["job"]

    cv = (
        "Mario Rossi - Backend Developer\n\n"
        "Esperienza\n"
        "- Sviluppato servizi in Python con FastAPI per la piattaforma pagamenti\n"
        "- Ottimizzato query PostgreSQL riducendo la latenza del 40%\n"
        "- Gestito i deploy su Docker\n"
        "- Partecipazione alle riunioni settimanali\n\n"
        "Competenze: Python, PostgreSQL, Docker, Git\n"
    )
    response = client.post(
        "/api/cv/review",
        files={"file": ("cv.txt", io.BytesIO(cv.encode("utf-8")), "text/plain")},
        data={"job_id": job["id"]},
    )
    assert response.status_code == 201
    review = response.json()["review"]
    assert "Python" in review["matched_keywords"]
    assert "Kafka" in review["missing_keywords"]
    assert review["suggestions"]

    assert client.get("/api/cv").json()["total"] == 1
    assert client.get(f"/api/cv/{review['id']}").status_code == 200
    assert client.delete(f"/api/cv/{review['id']}").status_code == 204
    assert client.get(f"/api/cv/{review['id']}").status_code == 404


def test_cv_in_formato_non_supportato(client):
    response = client.post(
        "/api/cv/review",
        files={"file": ("cv.pages", io.BytesIO(b"x" * 200), "application/octet-stream")},
    )
    assert response.status_code == 422


def test_cv_troppo_corto(client):
    response = client.post(
        "/api/cv/review",
        files={"file": ("cv.txt", io.BytesIO(b"ciao"), "text/plain")},
    )
    assert response.status_code == 422


def test_cancellazione_annuncio(client):
    job = client.post(
        "/api/jobs", json={"raw_text": SAMPLE_JOB, "research_company": False}
    ).json()["job"]
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_lacune_del_catalogo_sull_annuncio(client):
    job = client.post(
        "/api/jobs", json={"raw_text": SAMPLE_JOB, "research_company": False}
    ).json()["job"]

    response = client.get("/api/knowledge/gaps", params={"job_id": job["id"]})
    assert response.status_code == 200
    body = response.json()
    per_termine = {g["term"]: g for g in body["gaps"]}
    assert per_termine["Kubernetes"]["covered"] is False
    assert per_termine["Kafka"]["covered"] is True
    assert body["missing"] >= 1


def test_lacune_su_annuncio_inesistente(client):
    assert client.get("/api/knowledge/gaps", params={"job_id": "nope"}).status_code == 404


def test_aggiunta_argomento_al_catalogo_e_export(client):
    prima = client.get("/api/meta").json()["content"]["topics"]

    created = client.post(
        "/api/knowledge/topics",
        json={
            "term": "Kubernetes",
            "num_questions": 0,
            "draft": {
                "title": "Kubernetes per il colloquio",
                "summary": "Orchestratore di container basato su riconciliazione continua.",
                "category": "engineering",
                "tags": ["kubernetes", "k8s"],
                "key_points": ["Pod, Deployment, Service"],
                "interview_answer": "Lo descrivo come un loop di riconciliazione.",
            },
        },
    )
    assert created.status_code == 201
    topic = created.json()["topic"]
    assert topic["custom"] is True

    # È entrato nel catalogo ed è ricercabile.
    assert client.get("/api/meta").json()["content"]["topics"] == prima + 1
    found = client.get("/api/knowledge/topics", params={"q": "kubernetes"}).json()
    assert any(t["id"] == topic["id"] for t in found["topics"])
    assert client.get(f"/api/knowledge/topics/{topic['id']}").status_code == 200

    # Export pronto da committare in app/content/.
    export = client.get("/api/knowledge/export").json()
    assert export["count"] == 1
    assert "Kubernetes per il colloquio" in export["topics_yaml"]

    # Eliminabile, a differenza degli argomenti del repository.
    assert client.delete(f"/api/knowledge/topics/{topic['id']}").status_code == 204
    assert client.get("/api/meta").json()["content"]["topics"] == prima


def test_gli_argomenti_del_repository_non_si_eliminano(client):
    response = client.delete("/api/knowledge/topics/core-01-what-is-an-api")
    assert response.status_code == 409
    assert "YAML" in response.json()["detail"]


def test_aggiunta_senza_ai_e_senza_contenuto_da_400(client):
    response = client.post("/api/knowledge/topics", json={"term": "Kubernetes"})
    assert response.status_code == 400
    assert "modello AI" in response.json()["detail"]
