# Sviluppo locale

## Avvio rapido con Docker

```bash
cp .env.example .env     # opzionale: serve solo per attivare l'AI
docker compose up --build
```

Frontend su http://localhost:5173, API su http://localhost:8000,
documentazione interattiva su http://localhost:8000/docs.

## Avvio senza Docker

Due terminali.

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Vite proxa `/api` verso `http://127.0.0.1:8000`, quindi in sviluppo non serve
configurare né CORS né `VITE_API_BASE_URL`.

In locale i dati finiscono in `backend/.data/`, un file JSON per documento.
Per ripartire da zero basta cancellare quella cartella.

## Attivare l'AI in locale

Serve un account Azure AI Foundry con un modello deployato. Nel `.env`:

```bash
AZURE_OPENAI_ENDPOINT=https://<risorsa>.openai.azure.com/
AZURE_OPENAI_API_KEY=<chiave>
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

Verifica con `curl -s localhost:8000/api/meta | grep ai_enabled`.

In Azure la chiave non serve: si usa la managed identity. In locale puoi
ottenere lo stesso effetto con `az login`, lasciando `AZURE_OPENAI_API_KEY`
vuota: `DefaultAzureCredential` userà le tue credenziali, a patto che tu abbia
il ruolo Cognitive Services OpenAI User sulla risorsa.

## Test

```bash
cd backend
pytest                     # 125 test
pytest -q --tb=short       # output compatto
pytest tests/test_planner.py -v
pytest -k idempotency      # per nome
ruff check . && ruff check --fix .
```

Cosa coprono:

| File | Oggetto |
|---|---|
| `test_knowledge.py` | Integrità del catalogo, riferimenti, scoring |
| `test_problems.py` | Ogni soluzione di riferimento passa i propri test |
| `test_jobs.py` | Estrazione euristica: stack, seniority, luogo, modalità |
| `test_planner.py` | Budget, binari, ancore, alternanza, niente quiz orfani |
| `test_quiz.py` | Selezione, mescolamento delle opzioni, correzione |
| `test_curator.py` | Lacune, creazione, persistenza, export |
| `test_cv.py` | Estrazione testo, gap keyword, revisione euristica |
| `test_storage.py` | Repository su file |
| `test_sandbox.py` | Esecuzione del codice utente e casi di fallimento |
| `test_api.py` | Percorsi end-to-end attraverso l'API |
| `test_auth.py` | Codice di accesso |

I test girano **senza AI**: le fixture forzano il client non configurato, così
si verifica il comportamento deterministico e la suite resta veloce e gratuita.
Per il percorso AI si usa un finto client con risposta fissa (`_FakeAI` in
`test_curator.py`).

## Frontend

```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run build       # typecheck + bundle di produzione
npm run preview     # serve il bundle compilato
```

TypeScript è in `strict`, con `noUnusedLocals` e `noUnusedParameters`: la
build fallisce su un import non usato. È voluto.

## Terraform

```bash
cd terraform
terraform fmt -recursive
terraform init -backend=false && terraform validate
```

`validate` controlla la configurazione contro lo schema dei provider e non
richiede credenziali Azure. Per un `plan` reale serve `az login` e
`ARM_SUBSCRIPTION_ID`.

## Struttura del repository

```
backend/          API FastAPI, servizi, knowledge base, test
frontend/         SPA React + TypeScript
terraform/        Infrastruttura Azure
docs/             Questa documentazione
.github/workflows CI e deploy
docker-compose.yml
```

## Problemi ricorrenti

**Il frontend dice "Impossibile contattare l'API".**
L'API non è in esecuzione, oppure `VITE_API_BASE_URL` punta altrove. In
sviluppo va lasciata vuota: ci pensa il proxy di Vite.

**`pytest` fallisce su `test_sandbox.py`.**
Quei test usano `resource.setrlimit`, che esiste solo su Unix. Su altri sistemi
vengono saltati automaticamente.

**Un argomento aggiunto è sparito.**
In locale vive in `backend/.data/custom_topics/`. Se hai cancellato la
cartella, se n'è andato. Esporta e committa ciò che vuoi tenere.

**Un quiz sembra sempre uguale.**
Le domande vengono pescate dal catalogo: con pochi argomenti selezionati il
pool è piccolo. Allarga la selezione o attiva la generazione con l'AI.
