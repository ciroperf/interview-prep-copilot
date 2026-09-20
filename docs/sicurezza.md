# Sicurezza

L'app è pensata per un utente singolo. Le scelte qui sotto riflettono quel
contesto: sono adeguate a un progetto personale, non a un servizio multi-utente.

## Modello di accesso

Due modalità, scelte con `enable_entra_auth` nel Terraform.

### Login Microsoft (Entra ID) — consigliata

```hcl
enable_entra_auth       = true
entra_restrict_to_owner = true
```

Il flusso è **OAuth2 Authorization Code con PKCE**:

```
Browser
  │ 1. MSAL porta la scheda su login.microsoftonline.com
  │ 2. l'utente si autentica, torna un authorization code
  │ 3. MSAL lo scambia con un access token (PKCE, nessun client secret)
  ▼
Static Web App ──Authorization: Bearer <token>──► Container App
                                                   └ autenticazione integrata:
                                                     valida firma, issuer,
                                                     audience e scadenza
```

Chi fa cosa:

* **Terraform** crea l'app registration, espone lo scope `access_as_user`,
  registra gli URI di reindirizzamento e configura l'autenticazione integrata
  della Container App con `unauthenticatedClientAction = Return401`.
* **MSAL** nel frontend ottiene e rinnova il token, con il flusso a
  *redirect*: stessa scheda, nessun popup da sbloccare. Il token sta in
  `sessionStorage`, non in `localStorage`: non sopravvive alla chiusura del
  browser.
* **L'autenticazione integrata di Container Apps** valida il token *prima* che
  la richiesta arrivi all'applicazione, e inietta l'identità negli header
  `X-MS-CLIENT-PRINCIPAL-*`.
* **Il backend** non verifica firme: si fida di quegli header, perché quel
  livello rimuove quelli eventualmente inviati dal client. Controlla solo che
  ci siano, il che intercetta una configurazione incompleta.

Con `entra_restrict_to_owner = true` entra **solo chi è assegnato
esplicitamente** all'applicazione, e Terraform assegna te. Con `false`, chiunque
abbia un account nel tuo tenant.

Due percorsi restano pubblici: `/api/health`, altrimenti le probe di Container
Apps prenderebbero 401 e la revisione non partirebbe mai, e `/api/meta`, che il
frontend interroga prima del login per sapere come autenticarsi. Nessuno dei due
espone dati riservati.

`entra_allow_azure_cli = true` (default) pre-autorizza anche la Azure CLI, così
`az account get-access-token` ottiene un token per l'API senza schermata di
consenso: è quello che usano gli script per verificare l'AI dopo un deploy. Non
allarga chi può entrare — con `entra_restrict_to_owner = true` serve comunque
l'assegnazione esplicita — ma se preferisci che nessun token sia ottenibile da
riga di comando, mettilo a `false`.

**Richiede** il permesso di creare app registration nel tenant. Se la tua
organizzazione lo vieta, chiedi a un amministratore oppure resta sul codice.

### Codice di accesso condiviso — default

Un codice confrontato a tempo costante con `hmac.compare_digest`, conservato dal
client in `localStorage` e inviato nell'header `X-Access-Code`.

Cosa protegge: impedisce a chi trova l'URL di usare la tua app e di consumare i
tuoi token. Cosa non fa: non distingue utenti, non ha scadenza, non ha revoca
selettiva.

Il codice lo genera Terraform se non lo specifichi:

```bash
terraform output -raw access_code
```

Passando a Entra, il codice smette di valere: un vecchio codice rimasto in giro
non diventa una scorciatoia.

## Segreti

Non ce ne sono nel codice né nell'immagine. In Azure:

* **Storage**: managed identity con i ruoli Storage Table Data Contributor e
  Storage Blob Data Contributor, assegnati solo su quell'account.
* **AI Foundry**: managed identity con Cognitive Services OpenAI User, che
  consente l'inferenza ma non la gestione dei deployment. Con
  `ai_use_managed_identity = true` (default) l'autenticazione locale con chiave
  è **disabilitata** sull'account.
* **Codice di accesso**: secret della Container App, non variabile in chiaro.

In locale la chiave dell'AI sta in `.env`, che è in `.gitignore`. Se ti scappa
un commit con una chiave dentro, **ruotala**: rimuoverla dal codice non basta,
resta nella storia di git.

### Le chiavi dello storage account

`shared_access_key_enabled` resta `true` di default. L'applicazione non le usa
mai, ma servono al provider Terraform per creare il container blob. Per
disattivarle:

1. Assegna a chi lancia l'apply il ruolo Storage Blob Data Contributor
   sull'account.
2. Aggiungi `storage_use_azuread = true` nel blocco `provider "azurerm"`.
3. Imposta `storage_shared_access_key_enabled = false`.

## Esecuzione del codice utente

`ENABLE_CODE_EXECUTION` è **false** di default, in locale e in Azure.

Quando è attiva, `services/sandbox.py` esegue il codice inviato in un processo
separato con interprete isolato (`python -I`), limiti su CPU, memoria e
dimensione dei file (`resource.setrlimit`) e un timeout esterno.

**Non è una sandbox di sicurezza.** In particolare non isola la rete e non
isola il filesystem: il codice eseguito può aprire connessioni in uscita e
leggere i file leggibili dall'utente del container.

Per questo il Terraform **rifiuta** `enable_code_execution = true` senza
`enable_entra_auth = true`: il codice di accesso condiviso non basta, perché è
un singolo segreto senza scadenza né revoca, e se gira diventa una shell remota
per chiunque lo possieda. Dietro il login Microsoft con
`entra_restrict_to_owner`, invece, l'unico che può eseguire codice sei tu, e il
rischio residuo è solo verso te stesso.

In locale la questione non si pone: basta `ENABLE_CODE_EXECUTION=true` nel
`.env`, perché l'app non è raggiungibile da fuori.

Per un'esecuzione sicura anche in scenari aperti servirebbe gVisor, una VM
dedicata, o l'esecuzione nel browser con Pyodide.

Con l'esecuzione disattivata il flusso resta utile: la soluzione viene valutata
dal modello rispetto alla consegna e ai casi limite, e senza AI si ricade sugli
hint del problema.

## Dati personali

Il CV è il dato più sensibile che l'app tocca.

* `store_cv_files = false` di default: il file viene letto in memoria,
  analizzato e **non salvato**. Resta solo il risultato della revisione.
* Con `store_cv_files = true` finisce in un container blob privato, con
  soft delete a 7 giorni.
* Il testo del CV viene inviato al modello **solo** se l'AI è configurata.
  Azure OpenAI non usa i dati dei clienti per addestrare i modelli, ma vale la
  pena saperlo prima di caricare un CV con dati di terzi.
* `DELETE /api/cv/{id}` cancella revisione e file associato.

## Superficie esposta

| Aspetto | Scelta |
|---|---|
| CORS | Solo l'origin della Static Web App più quelli dichiarati in `allowed_origins` |
| Header ammessi | `Content-Type` e `X-Access-Code` |
| Credenziali CORS | `allow_credentials = false`: non usiamo cookie |
| Upload | 5 MB, estensioni limitate a pdf/docx/txt/md |
| Ingress | Solo HTTPS, la porta 8000 non è esposta direttamente |
| Container | Utente non privilegiato (uid 10001), immagine slim |
| Soluzioni dei problemi | Rotta separata: non escono insieme al testo del problema |
| Risposte dei quiz | Mai inviate al client prima della consegna |

## Cosa manca, consapevolmente

* Nessun rate limiting applicativo. Con l'accesso protetto e un solo utente il
  rischio è il consumo di token, già limitato da `ai_capacity`.
* Nessun audit log delle azioni.
* Nessuna cifratura applicativa a riposo oltre a quella di Azure Storage.
* Nessuna scansione antivirus sui file caricati.

Sono lacune accettabili per un'app personale. Se un giorno diventasse
multi-utente, andrebbero affrontate prima di qualunque altra cosa — insieme
all'autenticazione vera.
