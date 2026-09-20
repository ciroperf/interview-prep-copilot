# Interview Prep Copilot

Da un annuncio di lavoro a un piano di studi su misura per quel colloquio.

Incolli il testo dell'offerta, l'app ne estrae ruolo, seniority, stack e
requisiti, e costruisce un piano diviso in **parte conoscitiva** (teoria da
saper raccontare, scheda azienda, domande comportamentali) e **parte tecnica**
(quiz, esercizi di coding, system design), tarato sui giorni e sui minuti che
hai davvero a disposizione.

```
  Annuncio  ─►  Analisi  ─►  Piano di studi  ─►  Quiz · Coding · CV
                   │              │
                   │              └─ conoscitiva  +  tecnica
                   └─ scheda azienda, requisiti pesati, lacune del catalogo
```

## Cosa fa

* **Analizza un annuncio** — ruolo, seniority, luogo, modalità, stack e
  requisiti con un peso di importanza da 1 a 5.
* **Costruisce un piano** — argomenti scelti e motivati sull'annuncio,
  distribuiti su un calendario che rispetta il tuo budget di tempo. Ciò che non
  ci sta viene escluso, a partire da quello che conta meno.
* **Prepara la scheda azienda** — settore, prodotti, processo di selezione
  tipico, punti da citare e domande intelligenti da fare.
* **Ti interroga** — 146 domande a risposta multipla sul catalogo, con le
  opzioni mescolate a ogni esecuzione e la spiegazione di ogni errore.
* **Ti fa scrivere codice** — 14 problemi in stile colloquio con test, hint
  progressivi e revisione della soluzione.
* **Rivede il CV** — confronto con l'annuncio, parole chiave mancanti,
  riscrittura delle voci deboli, domande che il CV provoca.
* **Cresce con te** — quando un annuncio chiede qualcosa che il catalogo non
  copre (Kubernetes, Terraform, Snowflake…), te lo segnala e genera la scheda
  mancante, che entra subito nei piani e nei quiz.

## Contenuti

**78 argomenti, 146 domande, 14 problemi di coding.**

I 40 concetti backend fondamentali (API e HTTP, database, caching, sistemi
distribuiti, affidabilità), 12 argomenti sui **pattern di strutturazione del
codice** (layered, repository, service layer, DTO, dependency injection,
esagonale, DDD, unit of work, GoF, organizzazione del progetto, CQRS, gestione
degli errori), 14 di algoritmi e strutture dati, più system design,
comportamentale, pratiche di ingegneria e linguaggi.

Ogni argomento ha una sintesi, i punti chiave, gli errori tipici, le possibili
domande di approfondimento e — la parte che conta di più — una
`interview_answer`: la risposta da dare a voce, in prima persona, con i
compromessi espliciti.

## Funziona anche senza AI

Con un modello Azure AI Foundry configurato l'app estrae i dati dall'annuncio,
motiva la scelta degli argomenti, genera schede nuove e rivede CV e codice.

Senza, funziona lo stesso: un dizionario di ~90 tecnologie e un sistema di
scoring deterministico producono comunque analisi, piano e quiz. Le funzioni
che richiedono il modello restano disabilitate, con la spiegazione del perché.

Vale anche come scelta economica: `enable_ai = false` azzera la voce di spesa
più grossa.

## Avvio in locale

```bash
git clone https://github.com/ciroperf/interview-prep-copilot.git
cd interview-prep-copilot
docker compose up --build
```

Frontend su http://localhost:5173, API su http://localhost:8000/docs.

Senza Docker, oppure per i dettagli su test e AI in locale, vedi
[docs/sviluppo-locale.md](docs/sviluppo-locale.md).

## Deploy su Azure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars && $EDITOR terraform.tfvars
terraform init && terraform apply
terraform output next_steps
```

Poi si pubblicano immagine dell'API e bundle del frontend; dalla seconda volta
ci pensano le GitHub Actions. Procedura completa, login federato OIDC e secret
da configurare: [docs/deploy.md](docs/deploy.md).

### Costo

**Circa 0,20 – 0,60 EUR al mese** per un uso personale.

| Servizio | Piano | Mensile |
|---|---|---|
| Static Web Apps | Free | 0 |
| Container Apps | Consumption, scale-to-zero | 0 (dentro il piano gratuito) |
| Storage Account | Standard LRS | ~0,05 |
| Log Analytics | quota 0,2 GB/giorno | 0 |
| AI Foundry | gpt-4o-mini a consumo | ~0,10 – 0,50 |

Lo scale-to-zero è la leva principale: fuori uso il container si spegne e non
costa nulla, al prezzo di qualche secondo di cold start sulla prima richiesta.
Il Terraform crea anche un budget con avvisi via email. Dettaglio di ogni voce
e delle alternative: [docs/costi.md](docs/costi.md).

## Architettura

```
Browser ─► Static Web App (React) ─► Container App (FastAPI) ─┬─► Table Storage
                                                              ├─► AI Foundry
                                                              └─► Log Analytics
```

Nessun segreto fra i componenti: la Container App usa una managed identity con
i ruoli RBAC minimi su storage e AI. L'unico segreto è il codice di accesso
dell'app.

* **Backend** — Python 3.12, FastAPI, Pydantic. I servizi non importano
  FastAPI: la logica si testa senza client HTTP.
* **Frontend** — React 18, TypeScript in `strict`, Vite. Nessuna libreria di UI
  né di state management.
* **Dati** — Table Storage in Azure, file JSON in locale, dietro lo stesso
  `Protocol`.
* **Infrastruttura** — Terraform, 18 risorse, `terraform validate` in CI.

Il ragionamento dietro le scelte, e il funzionamento del generatore di piani:
[docs/architettura.md](docs/architettura.md).

## Documentazione

| Documento | Contenuto |
|---|---|
| [architettura.md](docs/architettura.md) | Componenti, scelte e alternative scartate, come funziona il planner |
| [deploy.md](docs/deploy.md) | Terraform, immagine, frontend, GitHub Actions, OIDC |
| [costi.md](docs/costi.md) | Ogni voce di spesa e le leve per ridurla |
| [sicurezza.md](docs/sicurezza.md) | Accesso, segreti, esecuzione del codice utente, dati personali |
| [api.md](docs/api.md) | Le 23 rotte con esempi `curl` |
| [contenuti.md](docs/contenuti.md) | Formato della knowledge base e come estenderla |
| [sviluppo-locale.md](docs/sviluppo-locale.md) | Setup, test, problemi ricorrenti |

## Test

```bash
cd backend && pytest        # 125 test
```

Girano senza AI e senza rete: le fixture forzano il client non configurato, il
percorso AI si prova con un finto client. Fra le cose verificate: ogni
soluzione di riferimento supera i propri test, il piano sta nel budget, non
contiene quiz su argomenti che non ha in programma di studiare, e le opzioni
dei quiz sono davvero mescolate.

## Struttura

```
backend/
  app/
    api/routes/     una rotta per area: jobs, plans, quizzes, problems, cv, knowledge
    services/       logica di dominio: planner, curator, quiz, coding, cv, knowledge
    ai/             client Azure AI Foundry e prompt
    storage/        Repository: JSON in locale, Table Storage in Azure
    content/        la knowledge base, in YAML
  tests/
frontend/src/       pagine, componenti, client API tipizzato
terraform/          infrastruttura Azure
docs/
```

## Licenza

MIT — vedi [LICENSE](LICENSE).
