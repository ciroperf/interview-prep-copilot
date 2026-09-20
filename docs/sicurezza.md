# Sicurezza

L'app è pensata per un utente singolo. Le scelte qui sotto riflettono quel
contesto: sono adeguate a un progetto personale, non a un servizio multi-utente.

## Modello di accesso

Un **codice di accesso condiviso**, confrontato a tempo costante con
`hmac.compare_digest`. Il client lo conserva in `localStorage` e lo invia
nell'header `X-Access-Code`.

Cosa protegge: impedisce a chi trova l'URL di usare la tua app e di consumare i
tuoi token. Cosa non fa: non distingue utenti, non ha scadenza, non ha
revoca selettiva. `/api/health` resta pubblico perché serve alle probe.

Il codice lo genera Terraform se non lo specifichi:

```bash
terraform output -raw access_code
```

Per alzare l'asticella, Container Apps ha l'autenticazione integrata con Entra
ID, che si attiva senza toccare il codice dell'applicazione:

```bash
az containerapp auth microsoft update \
  --name <container-app> --resource-group <rg> \
  --client-id <app-id> --tenant-id <tenant> \
  --yes
az containerapp auth update --name <container-app> --resource-group <rg> \
  --unauthenticated-client-action RedirectToLoginPage
```

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

Attivala solo se: l'app gira in locale, oppure gira in Azure ma è protetta da
autenticazione vera e sei tu l'unico a usarla, e accetti che un errore nel
codice che scrivi possa toccare l'ambiente del container. Per un'esecuzione
sicura servirebbe gVisor, una VM dedicata, o l'esecuzione nel browser con
Pyodide.

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
