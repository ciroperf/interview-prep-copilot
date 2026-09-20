# API

Base URL: `https://<container-app>.azurecontainerapps.io/api`
Documentazione interattiva generata da FastAPI: `/docs` (OpenAPI su `/openapi.json`).

Tutte le rotte tranne `/api/health` e `/api/meta` richiedono l'header
`X-Access-Code`, se il codice di accesso è configurato.

## Sistema

| Metodo | Rotta | Descrizione |
|---|---|---|
| GET | `/health` | Liveness. Pubblica, senza I/O. |
| GET | `/meta` | Configurazione dell'istanza e conteggi del catalogo. |
| POST | `/ai/selftest` | Esegue una generazione minima e riferisce cosa ha funzionato. |

```bash
curl -s -X POST "$API/api/ai/selftest" -H "X-Access-Code: $CODE" | python3 -m json.tool
```

Il selftest è il modo rapido di verificare modello, versione dell'API e
permessi dopo un cambio di configurazione. Risponde `400` se l'AI non è
configurata; se la chiamata fallisce restituisce `ok: false` con l'errore e un
campo `hint` che dice cosa cambiare.

```bash
curl -s "$API/api/meta" | python3 -m json.tool
```

```json
{
  "ai_enabled": true,
  "ai_deployment": "gpt-4o-mini",
  "ai_auth": "managed_identity",
  "code_execution_enabled": false,
  "access_code_required": true,
  "storage_backend": "azure_tables",
  "content": { "topics": 78, "questions": 146, "problems": 14 }
}
```

## Annunci

| Metodo | Rotta | Descrizione |
|---|---|---|
| POST | `/jobs` | Analizza il testo di un annuncio e lo salva. |
| GET | `/jobs` | Elenco sintetico. |
| GET | `/jobs/{id}` | Dettaglio completo. |
| POST | `/jobs/{id}/company` | Rigenera solo la scheda azienda. |
| DELETE | `/jobs/{id}` | Elimina. |

```bash
curl -s -X POST "$API/api/jobs" \
  -H 'Content-Type: application/json' -H "X-Access-Code: $CODE" \
  -d '{"raw_text": "Senior Backend Engineer…", "company_name": "Acme", "research_company": true}'
```

Il corpo richiede almeno 30 caratteri in `raw_text`. La risposta contiene
`role_title`, `seniority`, `tech_stack`, `requirements` con l'importanza da 1 a
5, `responsibilities`, `interview_focus` e la `company`.

## Piani di studio

| Metodo | Rotta | Descrizione |
|---|---|---|
| POST | `/plans` | Genera un piano per un annuncio. |
| GET | `/plans?job_id=` | Elenco, filtrabile per annuncio. |
| GET | `/plans/{id}` | Piano, avanzamento e calendario. |
| PATCH | `/plans/{id}/items/{item_id}` | Cambia lo stato di un'attività. |
| DELETE | `/plans/{id}` | Elimina. |

```bash
curl -s -X POST "$API/api/plans" \
  -H 'Content-Type: application/json' -H "X-Access-Code: $CODE" \
  -d '{"job_id": "job_abc", "days": 7, "daily_minutes": 90,
       "known_strengths": ["Python"], "weak_areas": ["system design"], "use_ai": true}'
```

La risposta ha quattro sezioni: `plan` (con gli `items`), `progress`,
`by_track` (statistiche separate per binario conoscitivo e tecnico) e `by_day`
(il calendario già raggruppato).

Stati possibili di un'attività: `todo`, `in_progress`, `done`, `skipped`.

## Knowledge base

| Metodo | Rotta | Descrizione |
|---|---|---|
| GET | `/knowledge/categories` | Categorie con i conteggi. |
| GET | `/knowledge/topics` | Elenco, filtrabile per `category`, `track`, `q`. |
| GET | `/knowledge/topics/{id}` | Argomento completo. |
| GET | `/knowledge/gaps?job_id=` | Competenze dell'annuncio senza argomento dedicato. |
| POST | `/knowledge/topics` | Aggiunge un argomento al catalogo. |
| DELETE | `/knowledge/topics/{id}` | Elimina un argomento aggiunto (non quelli del repo). |
| GET | `/knowledge/export` | Argomenti aggiunti, nel formato dei file YAML. |

Rilevare e colmare una lacuna:

```bash
curl -s "$API/api/knowledge/gaps?job_id=job_abc" -H "X-Access-Code: $CODE"
```

```json
{ "missing": 3,
  "gaps": [
    {"term": "Kubernetes", "importance": 4, "covered": false,
     "coverage_score": 4.0, "best_topic_title": "Fondamenti di cloud e container"},
    {"term": "Kafka", "importance": 3, "covered": true,
     "best_topic_title": "Message queue (Kafka, RabbitMQ, SQS)"}
  ]}
```

Con l'AI configurata basta il termine:

```bash
curl -s -X POST "$API/api/knowledge/topics" \
  -H 'Content-Type: application/json' -H "X-Access-Code: $CODE" \
  -d '{"term": "Kubernetes", "job_id": "job_abc", "num_questions": 3}'
```

Senza AI si passa il contenuto in `draft`:

```bash
curl -s -X POST "$API/api/knowledge/topics" \
  -H 'Content-Type: application/json' -H "X-Access-Code: $CODE" \
  -d '{"term": "Kubernetes", "num_questions": 0,
       "draft": {"title": "Kubernetes per il colloquio",
                 "summary": "Orchestratore di container…",
                 "key_points": ["Pod, Deployment, Service"],
                 "interview_answer": "Lo descrivo come…"}}'
```

Risponde `400` se manca sia l'AI sia il `draft`, e `409` se si prova a
cancellare un argomento che arriva dai file YAML del repository.

## Quiz

| Metodo | Rotta | Descrizione |
|---|---|---|
| POST | `/quizzes` | Crea un quiz. |
| GET | `/quizzes` | Elenco con punteggi. |
| GET | `/quizzes/{id}` | Quiz, con il risultato se già consegnato. |
| POST | `/quizzes/{id}/submit` | Consegna e correzione. |

Le opzioni vengono **mescolate a ogni creazione** e la risposta corretta non
lascia mai il server prima della consegna. Una seconda consegna risponde `409`.

```bash
curl -s -X POST "$API/api/quizzes" \
  -H 'Content-Type: application/json' -H "X-Access-Code: $CODE" \
  -d '{"job_id": "job_abc", "num_questions": 10, "use_ai": false}'

curl -s -X POST "$API/api/quizzes/quiz_xyz/submit" \
  -H 'Content-Type: application/json' -H "X-Access-Code: $CODE" \
  -d '{"answers": [{"question_id": "q-core-04-a", "selected_index": 2}]}'
```

Una domanda senza risposta vale come errore (`selected_index` = -1).

## Esercizi di coding

| Metodo | Rotta | Descrizione |
|---|---|---|
| GET | `/problems?job_id=&difficulty=` | Elenco, ordinato per pertinenza. |
| GET | `/problems/{id}` | Consegna, esempi, hint e test visibili. |
| POST | `/problems/{id}/submit` | Invia una soluzione e ricevi la revisione. |
| GET | `/problems/{id}/solution` | Soluzione di riferimento, su rotta separata. |

```bash
curl -s -X POST "$API/api/problems/p-two-sum/submit" \
  -H 'Content-Type: application/json' -H "X-Access-Code: $CODE" \
  -d '{"problem_id": "p-two-sum", "code": "def two_sum(nums, target):\n    ..."}'
```

La revisione contiene `verdict`, `correctness`, `complexity`, `strengths`,
`improvements` e, se l'esecuzione è attiva, l'esito test per test.

## CV

| Metodo | Rotta | Descrizione |
|---|---|---|
| POST | `/cv/review` | Carica un CV e ottieni la revisione. |
| GET | `/cv` | Elenco delle revisioni. |
| GET | `/cv/{id}` | Revisione completa. |
| DELETE | `/cv/{id}` | Elimina revisione ed eventuale file. |

```bash
curl -s -X POST "$API/api/cv/review" -H "X-Access-Code: $CODE" \
  -F "file=@curriculum.pdf" -F "job_id=job_abc"
```

Formati: `.pdf`, `.docx`, `.txt`, `.md`, fino a 5 MB. Un PDF scansionato
restituisce `422` con la spiegazione: non contiene testo estraibile.

## Errori

| Codice | Significato |
|---|---|
| 400 | Input non valido a livello applicativo (es. AI richiesta ma non configurata) |
| 401 | Codice di accesso mancante o errato |
| 404 | Risorsa inesistente |
| 409 | Conflitto: quiz già consegnato, argomento non eliminabile |
| 413 | File troppo grande |
| 422 | Validazione fallita, o file illeggibile |

Il corpo dell'errore è sempre `{"detail": "..."}`. Il client traduce gli errori
di validazione FastAPI, che sono liste, in una stringa leggibile.
