# Architettura

## Quadro d'insieme

```
   Browser
      │
      │  HTTPS
      ▼
┌──────────────────────┐        ┌────────────────────────────┐
│  Static Web App      │  API   │  Container App (API)       │
│  React + TypeScript  │───────▶│  FastAPI, Python 3.12      │
│  piano Free, CDN     │        │  min 0 repliche            │
└──────────────────────┘        └──────────┬─────────────────┘
                                           │ managed identity
                        ┌──────────────────┼──────────────────┐
                        ▼                  ▼                  ▼
              ┌──────────────────┐ ┌───────────────┐ ┌──────────────┐
              │ Storage Account  │ │ AI Foundry    │ │ Log Analytics│
              │ Table + Blob     │ │ gpt-4o-mini   │ │ quota 0,2 GB │
              └──────────────────┘ └───────────────┘ └──────────────┘
```

Nessun segreto viaggia fra i componenti: la Container App ha una managed
identity con i ruoli RBAC per storage e AI. L'unico segreto configurato è il
codice di accesso dell'applicazione.

## Perché questi componenti

| Scelta | Alternativa scartata | Motivo |
|---|---|---|
| Container Apps con scale-to-zero | App Service B1 | B1 costa ~13 EUR/mese sempre accesi; qui fuori uso si paga zero |
| Static Web Apps Free | Servire il frontend dalla stessa Container App | Il piano Free è gratuito, ha CDN e HTTPS e toglie traffico all'API |
| Table Storage | Cosmos DB, PostgreSQL | Cosmos serverless costa comunque più di ~0,05 EUR/GB; qui i dati sono pochi documenti |
| Managed identity | Chiavi in app settings | Niente segreti da ruotare né da perdere |
| Un solo container, un worker | Gunicorn multi-worker | La knowledge base sta in memoria: con N worker ci sarebbero N copie |

## Backend

```
backend/app/
├── main.py            # composizione dell'app, CORS, lifespan
├── config.py          # impostazioni da variabili d'ambiente
├── deps.py            # dependency injection e guardia sul codice di accesso
├── domain/models.py   # modelli Pydantic condivisi
├── api/routes/        # un modulo per area: jobs, plans, quizzes, problems, cv, knowledge
├── services/          # logica di dominio, senza dipendenze da FastAPI
├── ai/                # client Azure AI Foundry e prompt
├── storage/           # Repository: JSON in locale, Table Storage in Azure
└── content/           # knowledge base in YAML
```

Il layering segue le convenzioni descritte in `pat-01-layered-architecture`
della knowledge base: le rotte traducono HTTP, i servizi contengono le regole,
lo storage è dietro un `Protocol`. Nessun servizio importa FastAPI, e questo è
ciò che rende i test veloci: `services/` si prova senza client HTTP.

### Lo strato di persistenza

`storage/base.py` definisce due `Protocol`, `Repository` e `BlobStore`. Ci sono
due implementazioni:

* `JsonFileRepository` — un file per documento, scrittura atomica con rename.
  È il default in sviluppo e non richiede alcuna dipendenza esterna.
* `TableStorageRepository` — una tabella per collezione. Il documento viene
  serializzato in JSON e spezzato in proprietà da 30.000 caratteri, perché
  Table Storage limita ogni proprietà stringa a 64 KB.

La scelta avviene in `storage/factory.py` in base a `STORAGE_BACKEND`.

### Il generatore di piani

`services/planner.py` è il componente centrale. Il procedimento:

1. **Pesatura dei termini.** Requisiti, stack e responsabilità dell'annuncio
   diventano termini pesati; l'importanza dichiarata si traduce in ripetizioni.
2. **Scoring del catalogo.** `KnowledgeBase.score_topics` combina una mappa
   curata a mano (`TERM_HINTS`, da "kafka" a `dist-30-message-queues`) con la
   sovrapposizione di token, che copre i termini non mappati.
3. **Correzioni.** La seniority sposta i pesi (system design per i senior, DSA
   per i junior); i punti di forza dichiarati abbassano, le aree deboli alzano.
4. **Selezione.** Se l'AI è configurata sceglie e motiva fra i 34 argomenti più
   pertinenti; altrimenti le priorità derivano dal punteggio normalizzato.
5. **Ancore.** Alcuni temi entrano sempre: azienda, comportamentale, system
   design per i senior, e una quota di esercizi DSA per seniority.
6. **Costruzione delle attività.** Ogni argomento genera uno studio, e se
   prioritario anche un quiz; gli argomenti DSA generano esercizi di codice.
7. **Taglio al budget.** `giorni × minuti` è un tetto rigido. Lo studio viene
   prima della verifica: un quiz non entra se il suo argomento non c'è.
8. **Distribuzione.** Priorità alta nei primi giorni, alternanza fra teoria e
   pratica, spazio riservato al ripasso finale sull'ultimo giorno.

Il risultato è diviso in due binari: `knowledge` (teoria, azienda,
comportamentale) e `technical` (quiz, coding, system design).

### La knowledge base espandibile

Il catalogo versionato non può coprire tutto. `services/curator.py` colma le
lacune in tre passi:

1. `find_gaps` confronta le competenze dell'annuncio con il catalogo. Un
   termine è coperto solo se esiste un argomento **dedicato**, cioè con quel
   termine nel titolo: "Kafka" è coperto, "Kubernetes" no, perché compare solo
   dentro un argomento generico sul cloud.
2. `create_topic` genera la scheda con l'AI (o la accetta scritta a mano) e la
   registra nell'indice in memoria, aggiornando anche i suggerimenti dinamici:
   da quel momento il termine punta all'argomento nuovo.
3. Il documento viene persistito nella collezione `custom_topics` e ricaricato
   a ogni avvio dell'applicazione.

`GET /api/knowledge/export` restituisce quegli argomenti già nel formato dei
file di `app/content/`: si copiano nel repository e si committano per renderli
parte stabile del catalogo.

> **Vincolo sul numero di repliche.** L'indice della knowledge base vive nella
> memoria del processo. Con più repliche, un argomento aggiunto è visibile solo
> a quella che lo ha creato finché le altre non si riavviano. Per questo
> `max_replicas` è 1 di default. Per andare oltre servirebbe un evento di
> invalidazione condiviso (per esempio via Redis pub/sub).

## Frontend

React 18 con TypeScript, Vite e react-router. Nessuna libreria di UI né di
state management: le schermate sono poche e il costo di manutenzione di un
design system scritto a mano (`src/styles.css`, circa 370 righe) è minore di
quello di una dipendenza in più.

* `lib/api.ts` — unico punto di contatto con l'API: base URL, codice di accesso,
  traduzione degli errori di validazione FastAPI in messaggi leggibili.
* `components/useAsync.ts` — hook che tiene insieme dati, caricamento, errore e
  ricarica, con protezione contro gli aggiornamenti dopo lo smontaggio.
* `components/ui.tsx` — componenti di presentazione condivisi.

L'URL dell'API è una variabile di **build** (`VITE_API_BASE_URL`), compilata nel
bundle: cambiarla richiede una nuova build, non un riavvio.

### Il client AI si adatta al modello

`ai/client.py` non contiene una tabella di modelli da aggiornare a ogni
release. Parte da un'ipotesi ricavata dal nome del deployment — i prefissi `o1`,
`o3`, `o4`, `gpt-5` indicano la famiglia reasoning — e costruisce la chiamata di
conseguenza: `max_completion_tokens` invece di `max_tokens`, niente
`temperature`, ruolo `developer` al posto di `system`, più `reasoning_effort` se
configurato.

Se l'ipotesi è sbagliata, la correzione arriva dall'errore: `adapt_style` legge
il messaggio dell'API, capisce quale parametro è stato rifiutato e propone uno
stile corretto. Il ciclo in `_create` riprova fino a quattro volte, una per
parametro negoziabile, e poi **ricorda** lo stile: le chiamate successive
costano una richiesta sola.

Gli errori non negoziabili — quota esaurita, autenticazione, rete — vengono
propagati immediatamente, senza tentativi inutili.

Il vantaggio pratico: un modello uscito dopo questo repository funziona senza
modifiche al codice, e cambiarlo è solo un `terraform apply`.

## Funzionamento senza AI

Ogni funzione ha un percorso deterministico che non richiede un modello:

| Funzione | Con AI | Senza AI |
|---|---|---|
| Analisi dell'annuncio | Estrazione strutturata | Dizionario di ~90 tecnologie, pattern per seniority, luogo e modalità |
| Scheda azienda | Generata | Domande da fare predefinite e istruzioni per la ricerca manuale |
| Piano di studi | Selezione motivata | Scoring deterministico sul catalogo |
| Quiz | Domande generate in più | 146 domande del catalogo |
| Revisione del codice | Analisi della soluzione | Esito dei test più gli hint del problema |
| Revisione del CV | Analisi mirata | Copertura keyword, voci senza risultato, lunghezza |
| Nuovi argomenti | Generati | Scrittura manuale dalla pagina Argomenti |

L'app parte e funziona anche senza `AZURE_OPENAI_ENDPOINT`. La barra in alto
mostra "AI non attiva" e le funzioni che richiedono il modello restano
disabilitate con una spiegazione.
