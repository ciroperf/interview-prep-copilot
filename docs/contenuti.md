# La knowledge base

I contenuti sono la parte che dà valore all'app: il piano di studi può essere
generato benissimo, ma se dietro non c'è materiale serio non serve a niente.

## Cosa c'è

| Categoria | Argomenti | Cosa copre |
|---|---|---|
| `core-concepts` | 10 | API, REST vs GraphQL, metodi e status code HTTP, stateless, auth, JWT, OAuth, rate limiting, idempotenza |
| `databases` | 10 | SQL vs NoSQL, indici, ACID, isolamento, normalizzazione, paginazione, sharding, replica, duplicati, locking |
| `caching` | 5 | Dove cachare, eviction, coerenza, CDN, quando la cache rende sbagliato un sistema |
| `distributed` | 5 | Load balancing, scaling, microservizi vs monolite, comunicazione, code |
| `reliability` | 10 | Semantiche di consegna, retry e circuit breaker, race condition, lock distribuiti, eventi, saga, degrado, observability, deploy, picchi |
| `patterns` | 12 | Livelli, repository, service layer, DTO, DI, esagonale, DDD, unit of work, GoF, struttura del progetto, CQRS, gestione errori |
| `dsa` | 14 | Complessità, array, hash map, stringhe, ricerca binaria, liste, stack, alberi, grafi, heap, DP, sliding window, backtracking, ordinamento |
| `system-design` | 2 | Metodo per il colloquio, design ricorrenti |
| `behavioral` + `company` | 3 | Metodo STAR, ricerca sull'azienda, negoziazione |
| `engineering` | 5 | Testing, git, cloud, sicurezza applicativa, qualità del codice |
| `languages` | 23 | Due schede introduttive, i percorsi dedicati a Python (7) e a JavaScript/TypeScript (8), più Java e Spring Boot (6) |
| `frontend` | 6 | React (rendering e stato), Angular, CSS e layout, prestazioni percepite, testing dei componenti |

Totale: **105 argomenti, 13 percorsi, 146 domande a risposta multipla, 14
problemi di coding**.

Le prime cinque categorie ricalcano esattamente la checklist dei 40 concetti
backend da cui è nato il progetto.

## Quanto deve essere approfondito un argomento

`tests/test_content_depth.py` impone le soglie minime ai contenuti versionati
(non a quelli generati dall'AI da un annuncio, che nascono più magri):

| Campo | Minimo |
|---|---|
| `deep_dive` | 900 caratteri |
| `key_points` | 6 voci |
| `examples` | almeno uno |
| `follow_ups` | 3, ognuna con la sua `answer` |
| `interview_answer` | 200 caratteri |
| `senior_signals`, `trade_offs`, `pitfalls`, `related` | non vuoti |

I `related` devono puntare a id esistenti e gli URL delle risorse devono essere
`https://`. Sono soglie, non obiettivi: un argomento può e deve andare oltre.

## Struttura di un argomento

```yaml
- id: core-10-idempotency          # stabile: piani e quiz lo referenziano
  title: Idempotenza (specialmente nei pagamenti)
  category: core-concepts
  track: knowledge                 # knowledge = si studia, technical = si esercita
  level: medium                    # easy | medium | hard
  tags: [api, affidabilita, pagamenti]
  estimated_minutes: 30
  summary: >-
    Un'operazione è idempotente se eseguirla più volte lascia il sistema…
  key_points:
    - "Il problema reale: il client va in timeout e non sa se…"
  deep_dive: |-
    La spiegazione lunga: è la parte che si studia, non che si ripassa.
    Almeno 900 caratteri, in paragrafi.
  key_points:
    - "Almeno sei, ognuno una cosa sola"
  examples:
    - title: Il caso che si porta al colloquio
      language: python                 # o text, sql, bash, javascript…
      code: |
        # Commenti in italiano, come nel resto del progetto.
      note: >-
        Perché questo esempio conta.
  trade_offs:
    - option: La scelta
      pros: Cosa dà
      cons: Cosa costa
      when: Quando conviene
  numbers:
    - "I numeri da citare a voce: soglie, ordini di grandezza, costi"
  interview_answer: >-
    Il caso che uso per spiegarlo è il pagamento: il client manda…
  senior_signals:
    - "Cosa distingue chi ha esperienza vera su questo tema"
  pitfalls:
    - "Controllare l'esistenza della chiave PRIMA della transazione…"
  follow_ups:
    - question: Cosa succede se due richieste con la stessa idempotency key…
      answer: >-
        La risposta, perché una domanda senza risposta lascia il lavoro a metà.
  related: [core-09-rate-limiting-throttling, db-19-duplicate-records]
  resources:
    - title: "Stripe - Idempotent requests"
      url: "https://docs.stripe.com/api/idempotent_requests"
      kind: doc
```

`interview_answer` è il campo che fa la differenza: è scritto in prima persona,
come lo diresti a voce. Non è un riassunto della teoria ma una risposta da
colloquio, con i compromessi espliciti e le esperienze citate al posto giusto.

## Struttura di una domanda

```yaml
- id: q-core-10-a
  topic_id: core-10-idempotency    # deve esistere, i test lo verificano
  difficulty: hard
  prompt: "Per implementare correttamente una idempotency key…"
  options: ["…", "…", "…", "…"]    # esattamente quattro
  answer_index: 1
  explanation: "Solo il vincolo unique dentro la stessa transazione…"
```

> Le opzioni vengono **mescolate a runtime** da `QuizService`. Nei file la
> risposta corretta sta quasi sempre in posizione 1, ed è un bias inevitabile
> di chi scrive: senza il mescolamento, rispondere sempre B darebbe il 95%.
> Non preoccuparti della posizione quando scrivi una domanda nuova.

## Struttura di un problema di coding

```yaml
- id: p-two-sum
  title: Two Sum
  topic_ids: [dsa-03-hash-maps]
  difficulty: easy
  target_complexity: "O(n) tempo, O(n) spazio"
  statement: |
    Dato un array di interi `nums`…
  function_name: two_sum            # deve comparire in starter_code e solution
  starter_code: |
    def two_sum(nums: list[int], target: int) -> list[int]:
        pass
  hints:                            # dal più vago al più esplicito
    - "La soluzione ingenua con due cicli annidati è O(n^2)…"
  tests:
    - kwargs: {nums: [2, 7, 11, 15], target: 9}
      expected: [0, 1]
    - kwargs: {nums: [0, 4, 3, 0], target: 0}
      expected: [0, 3]
      hidden: true                  # non mostrato al candidato
  solution: |
    def two_sum(nums: list[int], target: int) -> list[int]:
        ...
```

La suite verifica che **ogni soluzione di riferimento superi tutti i propri
test**: se aggiungi un problema con una soluzione sbagliata, la CI lo dice.

## Aggiungere contenuti

### Dall'app, partendo da un annuncio

È la strada più rapida e quella pensata per l'uso quotidiano:

1. Analizza un annuncio.
2. Sulla pagina dell'annuncio, **Copertura del catalogo → Verifica**.
3. Le competenze senza un argomento dedicato compaiono come lacune, ordinate
   per importanza. **Aggiungi al catalogo** genera la scheda con l'AI.
4. L'argomento entra subito nei piani, nei quiz e nella ricerca.

Senza AI configurata puoi scrivere la scheda a mano da **Argomenti → Scrivi un
argomento**.

### Rendere permanente ciò che hai aggiunto

Gli argomenti aggiunti vivono nello storage, non nel repository: sopravvivono
ai riavvii ma non a un `terraform destroy`. Per consolidarli:

1. **Argomenti → Esporta aggiunti**: scarica `topics_custom.yaml` e
   `questions_custom.yaml`.
2. Copiali in `backend/app/content/`.
3. `cd backend && pytest` — i test validano riferimenti, struttura e unicità
   degli id.
4. Committa.

Da quel momento fanno parte del catalogo stabile, e puoi eliminarli dallo
storage per evitare duplicati.

### A mano, direttamente nei file

I file sono caricati per glob: `topics_*.yaml` per gli argomenti,
`questions_*.yaml` per le domande, `problems.yaml` per gli esercizi e
`packs.yaml` per i percorsi. Puoi crearne di nuovi senza registrarli da nessuna
parte.

```bash
$EDITOR backend/app/content/topics_miei.yaml
cd backend && pytest tests/test_knowledge.py -q
```

## Aggiungere un percorso

Un percorso raggruppa argomenti già esistenti su un macroargomento e ci
aggiunge le fonti da cui approfondire. Vive in `packs.yaml`:

```yaml
- id: pack-kubernetes
  title: Kubernetes da colloquio
  subtitle: Pod, servizi, deploy e cosa si rompe davvero
  summary: >-
    Due o tre frasi su cosa copre il percorso e in che ordine.
  for_whom: A chi serve e a chi no.
  level: medium              # easy | medium | hard
  tags: [kubernetes, cloud]
  prerequisites:
    - Fondamenti di container
  topic_ids:                 # l'ordine è l'ordine di studio
    - eng-03-cloud-basics
  sources:
    - title: Documentazione ufficiale di Kubernetes
      url: https://kubernetes.io/docs/home/
      kind: doc              # doc | book | repo | article | practice | video | course
      note: >-
        Il motivo per cui questa fonte vale il tempo che costa. Senza il
        motivo la fonte è solo un link, e il percorso perde il suo scopo.
```

Un `topic_ids` che non esiste fa fallire il caricamento all'avvio: è voluto,
così un refuso si scopre subito e non a pagina aperta.

## Collegare un termine a un argomento

Perché "Kafka" in un annuncio porti all'argomento sulle code, serve una voce
in `TERM_HINTS` dentro `backend/app/services/knowledge.py`:

```python
"kafka": ["dist-30-message-queues", "rel-35-event-driven", "rel-31-delivery-semantics"],
```

Senza la voce il collegamento avviene comunque, ma solo per sovrapposizione di
token fra il termine e il testo dell'argomento: funziona quando il termine
compare nel titolo o nei tag, molto meno negli altri casi.

Gli argomenti aggiunti a runtime non hanno questo problema: il curator registra
automaticamente il termine di origine nei suggerimenti dinamici, con un peso
più alto di `TERM_HINTS` proprio perché sono stati creati apposta per quel
termine.

## Come è scritto il materiale

Qualche criterio seguito, utile se vuoi mantenere l'insieme coerente:

* **Niente definizioni da manuale.** Ogni argomento parte dal problema che
  risolve, non da cos'è.
* **I compromessi sono il contenuto.** "Dipende" è una risposta accettabile in
  colloquio solo se spieghi da cosa dipende.
* **Errori concreti.** I `pitfalls` sono cose viste in codice reale, non
  categorie astratte.
* **Termini tecnici in inglese**, spiegazioni in italiano: è come si parla
  davvero in un colloquio in Italia.
* **I distrattori dei quiz devono essere plausibili.** Un'opzione palesemente
  assurda rende la domanda inutile.
