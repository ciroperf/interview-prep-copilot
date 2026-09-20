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

Ottieni nome, versione, **tutte le SKU** e la capacità massima di ogni modello
di chat deployabile lì. Lo script esclude di proposito embedding, sintesi
vocale, trascrizione, immagini, video, audio e realtime: sono nel catalogo ma a
questa app non servono.

> **Guarda le SKU, non solo il nome.** Il Terraform usa `GlobalStandard` di
> default, ma non tutti i modelli la offrono. Se nell'elenco un modello mostra
> solo `Standard`, devi impostare anche:
> ```hcl
> ai_deployment_sku = "Standard"
> ```
> altrimenti l'apply fallisce con un errore di SKU non valida.

> `ai_location` può essere diversa da `location`. Puoi tenere l'app a Sweden
> Central e il modello dove c'è, senza spostare nient'altro.

## Leggere i nomi

Il catalogo segue uno schema abbastanza regolare, e riconoscerlo evita di
provare a caso:

| Suffisso | Cosa significa | Adatto a questa app |
|---|---|---|
| `-nano` | Il più piccolo e veloce della generazione | Solo se il costo è l'unica cosa che conta |
| `-mini` | Fascia media: buon rapporto qualità/prezzo | **Sì, è il punto d'equilibrio** |
| *nessun suffisso* | Il modello pieno | Sì, se la qualità vale il costo |
| `-pro` | Il più capace, molto più lento e caro | Sproporzionato qui |
| `-chat` | Variante conversazionale, **non ragiona** | Sì: più veloce del pari-nome che ragiona |
| `-codex` | Specializzato sulla scrittura di codice | No: qui il codice si *rivede*, non si scrive |
| `model-router` | Sceglie da solo il modello per ogni richiesta | Possibile, ma il costo diventa imprevedibile |

Le varianti `-chat` sono trattate dall'app come famiglia **standard**: accettano
`temperature` e non spendono token in ragionamento. Le altre della famiglia 5 e
le `o*` sono **reasoning**.

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

Un `-mini` della generazione 5 più recente che trovi nell'elenco:

```hcl
ai_model_name       = "gpt-5-mini"
ai_model_version    = "2025-08-07"          # o la più recente dall'elenco
ai_deployment_sku   = "GlobalStandard"      # verifica nell'elenco
ai_api_version      = "2025-01-01-preview"  # obbligatoria: è reasoning
ai_reasoning_effort = "low"
ai_capacity         = 20
```

Qualità nettamente superiore a `gpt-4o-mini` su revisione CV e codice, con
`reasoning_effort = "low"` che tiene la latenza ragionevole. È il punto in cui
si ferma la maggior parte dei progetti personali.

Se preferisci risposte immediate e ti basta un salto di qualità più contenuto,
la famiglia `4.1` non ragiona e resta velocissima:

```hcl
ai_model_name    = "gpt-4.1-mini"
ai_model_version = "2025-04-14"
ai_api_version   = "2024-10-21"     # GA, va bene: non è reasoning
```

### Massima qualità

Il modello pieno della generazione più recente, senza suffisso:

```hcl
ai_model_name       = "gpt-5"
ai_model_version    = "2025-08-07"          # o la più recente dall'elenco
ai_api_version      = "2025-01-01-preview"
ai_reasoning_effort = "medium"
ai_capacity         = 20
```

Metti in conto risposte da 10-30 secondi sulle operazioni pesanti come la
revisione del CV. L'app ha un timeout di 90 secondi, quindi c'è margine.
I `-pro` esistono ma qui sono sproporzionati: costano molto di più per un
guadagno che su questi compiti non si nota.

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

Verifica subito dopo, con una generazione vera:

```powershell
$api  = terraform output -raw api_url
$code = terraform output -raw access_code
curl.exe -s -X POST "$api/api/ai/selftest" -H "X-Access-Code: $code"
```

Con `enable_entra_auth = true` il codice non vale più: l'autenticazione
integrata risponde 401 a qualunque richiesta senza Bearer. Il token lo chiedi
alla Azure CLI, già autenticata come te:

```powershell
$api    = terraform output -raw api_url
$client = terraform output -raw entra_client_id
$token  = az account get-access-token --resource "api://$client" --query accessToken -o tsv
curl.exe -s -X POST "$api/api/ai/selftest" -H "Authorization: Bearer $token"
```

`.\scripts\update-api.ps1` fa da solo la scelta fra i due, leggendo
`auth_mode` dagli output di Terraform.

```json
{ "ok": true, "deployment": "gpt-5-mini", "latency_ms": 1840,
  "family_guessed": "reasoning", "family_actual": "reasoning", "adapted": false,
  "style": { "token_param": "max_completion_tokens", "temperature": false } }
```

Cosa guardare:

* `ok: false` → il campo `hint` dice cosa cambiare, in italiano.
* `adapted: true` → l'ipotesi iniziale era sbagliata e il client si è corretto
  da solo. Funziona, ma la prima chiamata di ogni riavvio costa un tentativo in
  più: puoi eliminarlo fissando `ai_model_family` al valore in `family_actual`.
* `latency_ms` alto → abbassa `ai_reasoning_effort`.

Il selftest consuma pochi token, quindi puoi rilanciarlo tutte le volte che vuoi.

## Quanto conosco io e quanto devi verificare tu

Questo repository è stato scritto con una certa fotografia del catalogo. I
modelli usciti dopo non li conosco: non posso dirti se `gpt-5.6-terra` costa più
o meno di `gpt-5-mini`, né quanto sia più bravo.

Quello che **non** invecchia è il meccanismo: il client si adatta da solo alla
famiglia, e lo script ti dice cosa è deployabile oggi. Per il prezzo, l'unica
fonte affidabile è il
[calcolatore Azure](https://azure.microsoft.com/pricing/calculator/), sezione
Azure OpenAI, filtrando per il modello esatto.

Regola pratica che regge nel tempo: all'interno di una generazione, `nano` <
`mini` < *pieno* < `pro` per costo e per qualità, e le varianti `-chat` costano
meno delle pari-nome che ragionano, perché non pagano i token di ragionamento.

Se vuoi provare un modello nuovo senza rischi: cambialo in `terraform.tfvars`,
`terraform apply`, lancia il selftest. Se non ti convince, rimetti il
precedente e rilancia. Ogni giro dura un paio di minuti e non tocca né
l'immagine né il frontend.

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

**L'apply fallisce con un errore sulla SKU**
Il modello non offre `GlobalStandard`. Guarda la colonna `sku` nell'elenco e
imposta `ai_deployment_sku` a uno dei valori che compaiono lì.

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
