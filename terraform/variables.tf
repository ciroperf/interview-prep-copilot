# ---------------------------------------------------------------------------
# Identità della sottoscrizione e del progetto
# ---------------------------------------------------------------------------

variable "subscription_id" {
  description = "ID della sottoscrizione Azure. Se vuoto si usa ARM_SUBSCRIPTION_ID."
  type        = string
  default     = ""
}

variable "name_prefix" {
  description = "Prefisso dei nomi delle risorse. Corto: alcuni nomi Azure hanno limiti stretti."
  type        = string
  default     = "ipc"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,8}$", var.name_prefix))
    error_message = "Solo minuscole e cifre, da 2 a 9 caratteri, iniziando con una lettera."
  }
}

variable "environment" {
  description = "Nome dell'ambiente, usato nei nomi e nei tag."
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Regione Azure per le risorse applicative."
  type        = string
  default     = "swedencentral"
}

variable "resource_group_name" {
  description = "Nome del resource group. Se vuoto viene derivato dal prefisso."
  type        = string
  default     = ""
}

variable "create_resource_group" {
  description = "false per usare un resource group già esistente."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tag applicati a tutte le risorse."
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# Applicazione
# ---------------------------------------------------------------------------

variable "container_image" {
  description = <<-EOT
    Immagine dell'API. Al primo apply l'immagine non esiste ancora, quindi il
    default è l'immagine di esempio di Microsoft: il workflow di deploy la
    sostituisce con quella vera. Terraform ignora le modifiche successive a questo
    campo, così un apply non fa tornare indietro la versione deployata.
  EOT
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "access_code" {
  description = <<-EOT
    Codice di accesso all'app. Se vuoto ne viene generato uno casuale, leggibile
    con `terraform output -raw access_code`. L'app è mono-utente: senza codice
    l'API resta aperta a chiunque conosca l'URL.
  EOT
  type        = string
  default     = ""
  sensitive   = true
}

variable "cpu" {
  description = "vCPU per replica. 0.25 è il minimo utile e il più economico."
  type        = number
  default     = 0.25
}

variable "memory" {
  description = "Memoria per replica. Deve stare nel rapporto 1 vCPU : 2 Gi."
  type        = string
  default     = "0.5Gi"
}

variable "min_replicas" {
  description = <<-EOT
    Repliche minime. 0 abilita lo scale-to-zero: fuori uso l'app non costa nulla,
    al prezzo di un cold start di qualche secondo sulla prima richiesta.
    Metti 1 solo se il cold start dà fastidio: costa circa 10-15 EUR/mese.
  EOT
  type        = number
  default     = 0
}

variable "max_replicas" {
  description = <<-EOT
    Repliche massime. Resta a 1 se non hai bisogno di concorrenza: gli argomenti
    aggiunti a runtime vivono nell'indice in memoria del processo, e con più
    repliche una nuova aggiunta sarebbe visibile solo a quella che l'ha creata
    finché le altre non si riavviano. Vedi docs/architecture.md.
  EOT
  type        = number
  default     = 1

  validation {
    condition     = var.max_replicas >= 1 && var.max_replicas <= 10
    error_message = "max_replicas deve essere fra 1 e 10."
  }
}

variable "enable_code_execution" {
  description = <<-EOT
    Esecuzione sul server del codice inviato dall'utente.

    Il runner isola il processo e limita CPU e memoria, ma NON isola la rete né
    il filesystem: chi può chiamare quell'endpoint esegue codice arbitrario
    dentro il container. Su un'app raggiungibile da internet significa
    consegnarla a chiunque riesca a entrare.

    Per questo è ammessa solo insieme a enable_entra_auth: dietro il login
    Microsoft, con entra_restrict_to_owner, l'unico che può eseguire codice sei
    tu. Vedi docs/sicurezza.md.
  EOT
  type        = bool
  default     = false

  validation {
    # Il codice utente gira solo dietro un'autenticazione vera. Il codice di
    # accesso condiviso non basta: è un singolo segreto, senza scadenza né
    # revoca, e se gira diventa una shell remota aperta a chi lo possiede.
    condition     = !var.enable_code_execution || var.enable_entra_auth
    error_message = <<-EOT
      enable_code_execution richiede enable_entra_auth = true.
      Eseguire codice arbitrario dietro il solo codice di accesso condiviso
      espone il container a chiunque venga in possesso di quel codice.
      In locale non serve nulla di tutto questo: basta ENABLE_CODE_EXECUTION=true
      nel file .env.
    EOT
  }
}

variable "store_cv_files" {
  description = "Conserva i CV caricati su Blob Storage. Di default vengono solo letti e scartati."
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Autenticazione
# ---------------------------------------------------------------------------

variable "enable_entra_auth" {
  description = <<-EOT
    true sostituisce il codice di accesso condiviso con il login Microsoft
    (Entra ID). Terraform crea l'app registration e configura l'autenticazione
    integrata di Container Apps; il frontend usa MSAL per ottenere il token.

    Richiede il permesso di creare app registration nel tenant. Se la tua
    organizzazione lo vieta, chiedi a un amministratore o resta sul codice.
  EOT
  type        = bool
  default     = false
}

variable "entra_restrict_to_owner" {
  description = <<-EOT
    true: entra solo chi viene assegnato esplicitamente all'applicazione, e
    Terraform assegna te. false: chiunque abbia un account nel tenant.
    Per un'app personale il valore giusto e' true.
  EOT
  type        = bool
  default     = true
}

variable "entra_allow_localhost" {
  description = <<-EOT
    Aggiunge http://localhost:5173 fra i redirect ammessi, per sviluppare il
    frontend in locale contro l'API vera. Toglilo se non ti serve.
  EOT
  type        = bool
  default     = true
}

variable "entra_extra_redirect_uris" {
  description = <<-EOT
    Altri URI di reindirizzamento, es. un dominio personalizzato.
    La slash finale la aggiunge il Terraform se manca: "https://x.it" diventa
    "https://x.it/", che è la forma che Entra ID pretende.
  EOT
  type        = list(string)
  default     = []
}

variable "storage_shared_access_key_enabled" {
  description = <<-EOT
    Chiavi dell'account storage. L'app non le usa mai (va di managed identity),
    ma servono al provider Terraform per creare il container blob. Metti false
    solo dopo aver dato a chi lancia l'apply il ruolo Storage Blob Data
    Contributor sull'account.
  EOT
  type        = bool
  default     = true
}

variable "allowed_origins" {
  description = <<-EOT
    Origin aggiuntivi ammessi dalla CORS.

    L'indirizzo gratuito della Static Web App (*.azurestaticapps.net) è già
    incluso automaticamente: non va elencato qui. Questa variabile serve solo
    se colleghi un dominio tuo, che è a pagamento. Senza, lasciala vuota.
  EOT
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# AI (Azure AI Foundry)
# ---------------------------------------------------------------------------

variable "enable_ai" {
  description = "false per non creare l'account AI: l'app resta usabile con le euristiche."
  type        = bool
  default     = true
}

variable "ai_location" {
  description = <<-EOT
    Regione dell'account AI. Il catalogo dei modelli varia per regione:
    swedencentral e eastus sono le più complete. Può differire da `location`.
  EOT
  type        = string
  default     = "swedencentral"
}

variable "ai_model_name" {
  description = <<-EOT
    Modello da deployare. Il default gpt-5-mini è il punto di equilibrio: ragiona,
    quindi va molto meglio di gpt-4o-mini su revisione del CV e del codice, ma
    costa una frazione del modello pieno.
    Verifica che ci sia nella tua regione con scripts/list-models.*
  EOT
  type        = string
  default     = "gpt-5-mini"
}

variable "ai_model_version" {
  description = <<-EOT
    Versione del modello. Deve esistere per il modello scelto: prendila
    dall'elenco di scripts/list-models.*, non tirarla a indovinare.
  EOT
  type        = string
  default     = "2025-08-07"
}

variable "ai_api_version" {
  description = <<-EOT
    Versione dell'API Azure OpenAI. 2024-10-21 è GA e copre la famiglia gpt-4o
    e gpt-4.1. I modelli reasoning (o3, o4-mini, gpt-5) richiedono i parametri
    max_completion_tokens e reasoning_effort, introdotti in una preview più
    recente: per loro serve una versione tipo 2025-01-01-preview o successiva.
    Se la versione impostata non esiste, il client non si arrende: il servizio
    risponde elencando quelle che accetta, e lui riprova con la più recente
    fra quelle. Lo segnala nei log e in /api/ai/selftest, così puoi fissare
    qui il valore giusto ed evitare il tentativo sprecato a ogni riavvio.
  EOT
  type        = string
  default     = "2025-01-01-preview"
}

variable "ai_model_family" {
  description = <<-EOT
    auto: la famiglia si deduce dal nome del deployment e si corregge da sola al
    primo errore dell'API. standard o reasoning la forzano, utile se hai dato al
    deployment un nome che non rivela il modello sottostante.
  EOT
  type        = string
  default     = "auto"

  validation {
    condition     = contains(["auto", "standard", "reasoning"], var.ai_model_family)
    error_message = "Valori ammessi: auto, standard, reasoning."
  }
}

variable "ai_reasoning_effort" {
  description = <<-EOT
    Quanto deve ragionare un modello reasoning: low, medium, high. Vuoto lascia
    il default del modello. Alzarlo migliora la qualità e alza il costo, perché
    i token di ragionamento si pagano come output.
    Ignorato dai modelli non reasoning.
  EOT
  type        = string
  default     = "low"

  validation {
    condition     = contains(["", "low", "medium", "high"], var.ai_reasoning_effort)
    error_message = "Valori ammessi: vuoto, low, medium, high."
  }
}

variable "ai_deployment_sku" {
  description = "GlobalStandard costa meno di Standard e non richiede capacità riservata."
  type        = string
  default     = "GlobalStandard"
}

variable "ai_capacity" {
  description = <<-EOT
    Capacità del deployment in migliaia di token al minuto. 10 = 10k TPM, più che
    sufficiente per un utente singolo e un tetto utile contro i consumi anomali.
  EOT
  type        = number
  default     = 20
}

variable "ai_use_managed_identity" {
  description = <<-EOT
    true: l'app si autentica con la managed identity, nessuna chiave in giro.
    false: usa la API key, comodo solo se devi chiamare l'endpoint da fuori Azure.
  EOT
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Registro immagini
# ---------------------------------------------------------------------------

variable "create_container_registry" {
  description = <<-EOT
    true crea un Azure Container Registry Basic (circa 4,60 EUR/mese).
    false (default) usa un registro pubblico come GHCR, che è gratuito: in quel
    caso ricordati di rendere pubblico il package su GitHub.
  EOT
  type        = bool
  default     = false
}

variable "registry_server" {
  description = "Registro da cui tirare l'immagine quando non si usa ACR."
  type        = string
  default     = "ghcr.io"
}

variable "registry_username" {
  description = "Utente del registro. Serve solo se il registro non è pubblico."
  type        = string
  default     = ""
}

variable "registry_password" {
  description = "Token del registro. Serve solo se il registro non è pubblico."
  type        = string
  default     = ""
  sensitive   = true
}

# ---------------------------------------------------------------------------
# Osservabilità e costi
# ---------------------------------------------------------------------------

variable "log_retention_days" {
  description = "Giorni di ritenzione dei log. 30 è il minimo fatturabile."
  type        = number
  default     = 30
}

variable "log_daily_quota_gb" {
  description = <<-EOT
    Tetto giornaliero di ingestione dei log, in GB. Oltre il tetto l'ingestione
    si ferma fino al giorno dopo: è la difesa contro una bolletta a sorpresa
    causata da un loop di errori.
  EOT
  type        = number
  default     = 0.2
}

variable "monthly_budget_eur" {
  description = "Budget mensile per gli avvisi di spesa. 0 disattiva il budget."
  type        = number
  default     = 15
}

variable "budget_alert_email" {
  description = "Email che riceve gli avvisi di budget. Obbligatoria se monthly_budget_eur > 0."
  type        = string
  default     = ""
}
