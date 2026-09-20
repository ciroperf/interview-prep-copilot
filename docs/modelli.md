# Scegliere il modello

Il default è `gpt-4o-mini`: economico e sufficiente per far funzionare tutto.
Questa pagina spiega quando conviene salire, quanto costa, e come cambiare
senza rompere niente.

## Prima di tutto: cosa hai davvero disponibile

Il catalogo dei modelli cambia nel tempo e **varia per regione**. Non fidarti di
una lista scritta in un file: chiedilo alla tua sottoscrizione.

```powershell
# Windows
cd terraform
.\scripts\list-models.ps1 -Location swedencentral
```

```bash
# macOS / Linux
cd terraform
./scripts/list-models.sh swedencentral
```

Ottieni nome, versione, SKU e capacità massima di ogni modello deployabile lì.
Se un modello che ti interessa non compare, prova un'altra regione: `eastus` e
`swedencentral` sono di solito le più complete.

> `ai_location` può essere diversa da `location`. Puoi tenere l'app a Sweden
> Central e il modello dove c'è, senza spostare nient'altro.

## Le due famiglie, e perché la distinzione conta

| | **Standard** (gpt-4o, gpt-4.1, …) | **Reasoning** (o3, o4-mini, gpt-5, …) |
|---|---|---|
| Come lavora | Risponde direttamente | Ragiona prima, poi risponde |
| `temperature` | Supportata | **Rifiutata** |
| Budget di output | `max_tokens` | `max_completion_tokens`, che include i token di ragionamento |
| Parametro di sforzo | — | `reasoning_effort`: low / medium / high |
| Latenza | Bassa | Da 3 a 10 volte più alta |
| Costo per risposta | Basso | Più alto: il ragionamento si paga come output |
| Dove rende | Estrazione, riscrittura, generazione di contenuti | Problemi con vincoli da rispettare tutti insieme |

L'app gestisce entrambe automaticamente: `backend/app/ai/client.py` parte da
un'ipotesi sul nome del deployment e, se l'API rifiuta un parametro, **legge
l'errore e si corregge**, ricordando lo stile per le chiamate successive.
Significa che anche un modello uscito dopo questo repository funziona senza
modifiche al codice.

Puoi verificare come ti ha classificato:

```bash
curl -s "$API/api/meta" | python -m json.tool
```

```json
{ "ai_deployment": "o4-mini", "ai_family": "reasoning",
  "ai_api_version": "2025-01-01-preview", "ai_max_output_tokens": 16000 }
```

## Dove il modello fa davvero la differenza

L'app chiama il modello in sei punti. Non tutti guadagnano allo stesso modo da
un modello più potente:

| Operazione | Guadagno salendo di modello | Perché |
|---|---|---|
| **Revisione del CV** | **Alto** | Deve tenere insieme CV, annuncio e keyword mancanti e proporre riscritture credibili. È il punto dove un modello debole produce consigli generici |
| **Revisione del codice** | **Alto** | Trovare il caso limite che rompe una soluzione è esattamente il compito su cui i reasoning brillano |
| **Generazione del piano** | Medio | Deve scegliere fra 34 argomenti rispettando un budget e motivare ogni scelta |
| **Scheda azienda** | Medio | Migliora la specificità, ma resta limitata da ciò che il modello sa dell'azienda |
| **Analisi dell'annuncio** | Basso | È estrazione strutturata: gpt-4o-mini la fa già bene |
| **Generazione quiz** | Basso | Le domande del catalogo sono scritte a mano e restano migliori |

Da qui una strategia sensata: **un modello medio come default, uno potente solo
dove serve**. Oggi l'app usa un solo deployment per tutto; se vuoi separarli,
il punto da toccare è `AIClient.complete_json`, che accetta già parametri per
chiamata.

## Tre configurazioni sensate

### Equilibrata — il consiglio se non sai cosa scegliere

```hcl
ai_model_name    = "gpt-4.1-mini"
ai_model_version = "<dalla lista>"
ai_api_version   = "2024-10-21"
ai_capacity      = 20
```

Qualità nettamente superiore a `gpt-4o-mini` su revisione CV e codice, latenza
ancora bassa, costo che resta nell'ordine di qualche decina di centesimi al
mese per uso personale.

### Massima qualità

```hcl
ai_model_name    = "gpt-4.1"        # oppure o4-mini / gpt-5, se disponibili
ai_model_version = "<dalla lista>"
ai_api_version   = "2024-10-21"     # reasoning: "2025-01-01-preview" o successiva
ai_capacity      = 20
```

Per un modello reasoning aggiungi:

```hcl
ai_reasoning_effort = "medium"      # low se la latenza dà fastidio
```

Metti in conto risposte da 10-30 secondi sulle operazioni pesanti come la
revisione del CV. L'app ha un timeout di 90 secondi, quindi c'è margine.

### Costo minimo

```hcl
ai_model_name = "gpt-4o-mini"       # il default
# oppure, per azzerare del tutto la voce AI:
enable_ai = false
```

Con `enable_ai = false` l'app resta pienamente utilizzabile: analizza l'annuncio
con il dizionario di tecnologie, costruisce il piano con lo scoring
deterministico, serve le 146 domande del catalogo e valuta il CV sulla copertura
delle parole chiave.

## Come si cambia

```powershell
cd terraform
notepad terraform.tfvars      # modifica ai_model_name, ai_model_version, ai_api_version
terraform apply
```

Terraform sostituisce il deployment del modello. **Non serve ricostruire
l'immagine né ripubblicare il frontend**: il nome del deployment e la versione
dell'API arrivano alla Container App come variabili d'ambiente, e l'app riparte
con una revisione nuova in una decina di secondi.

Verifica subito dopo:

```powershell
$api = terraform output -raw api_url
curl.exe -s "$api/api/meta"
```

Controlla che `ai_deployment` sia quello nuovo e che `ai_family` sia coerente.

## Quando qualcosa non va

**`max_tokens is not supported with this model`**
Hai messo un modello reasoning con una `ai_api_version` troppo vecchia. Il
client prova ad adattarsi, ma se l'API non conosce `max_completion_tokens` non
c'è niente da fare: alza `ai_api_version` a una preview recente.

**L'AI risponde vuoto, o l'app dice "la risposta non conteneva JSON valido"**
Tipico dei modelli reasoning: il ragionamento ha consumato tutto il budget di
output. Abbassa `ai_reasoning_effort` a `low`, oppure alza il budget nel backend
con `AI_REASONING_MAX_OUTPUT_TOKENS` (default 16000). L'errore dell'app dice
esplicitamente quale delle due provare.

**`DeploymentNotFound` / errore 404 sulle chiamate**
Il nome del deployment non coincide. Il Terraform chiama il deployment come il
modello, quindi `ai_model_name` e il nome del deployment devono corrispondere.
Controlla con:

```bash
az cognitiveservices account deployment list \
  --name <account-ai> --resource-group <rg> -o table
```

**L'apply fallisce con un errore di quota**
Ogni modello ha una quota TPM per regione, separata dalle altre. Abbassa
`ai_capacity`, oppure richiedi più quota dal portale AI Foundry, oppure scegli
un'altra regione in `ai_location`.

**Le risposte sono diventate lente**
È il prezzo dei reasoning. `ai_reasoning_effort = "low"` recupera gran parte
della latenza mantenendo quasi tutta la qualità.

## Modelli non OpenAI

L'account che il Terraform crea è di tipo `AIServices`, quindi dal portale AI
Foundry puoi deployare anche modelli di altri fornitori. Il client dell'app
parla il protocollo chat completions di Azure OpenAI: un modello che espone lo
stesso protocollo funziona cambiando solo `AZURE_OPENAI_DEPLOYMENT`. Uno che
espone un endpoint diverso richiederebbe un'implementazione a fianco di
`AIClient` — la logica dei servizi non cambierebbe, perché usa solo
`complete_json` e `complete_text`.
