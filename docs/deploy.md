# Deploy su Azure

Il deploy si fa in tre fasi: infrastruttura con Terraform, immagine dell'API,
bundle del frontend. Dalla seconda volta in poi ci pensano le GitHub Actions.

## Percorso rapido: uno script solo

Se non vuoi eseguire i passi a mano, `scripts/deploy.ps1` (Windows) e
`scripts/deploy.sh` (macOS/Linux) li fanno tutti in sequenza, verificando i
prerequisiti e aspettando che l'API risponda prima di dichiarare fatto.

```powershell
# Windows, dalla radice del repository
az login
.\scripts\deploy.ps1
```

Al primo avvio lo script crea `terraform/terraform.tfvars` dal template, lo apre
nel Notepad e si ferma: compila almeno `budget_alert_email`, salva e rilancia.

Per ripubblicare solo il codice, senza toccare l'infrastruttura:

```powershell
.\scripts\deploy.ps1 -SkipInfra
.\scripts\deploy.ps1 -SkipInfra -SkipWeb   # solo l'API
```

Lo script ha bisogno di:

| Strumento | Quando serve | Installazione su Windows |
|---|---|---|
| Azure CLI | sempre | `winget install Microsoft.AzureCLI` |
| Terraform | se non usi `-SkipInfra` | `winget install HashiCorp.Terraform` |
| Node.js 22 | se non usi `-SkipWeb` | `winget install OpenJS.NodeJS.LTS` |
| Docker Desktop | per costruire l'immagine in locale | `winget install Docker.DockerDesktop` |
| `$env:GITHUB_TOKEN` | per il push su GHCR | token con scope `write:packages` |

Senza Docker lo script salta il passo dell'immagine e te lo dice: in quel caso
la costruisce il workflow `deploy-backend.yml` al primo push su `main`.

Il resto di questa pagina spiega gli stessi passi uno per uno, utile quando
qualcosa non va o vuoi capire cosa sta succedendo.

## Prerequisiti

* Una sottoscrizione Azure e la Azure CLI (`az login`)
* Terraform ≥ 1.6
* Per l'AI: la sottoscrizione deve poter creare account Cognitive Services.
  Sulle sottoscrizioni nuove la quota per i modelli a volte va richiesta dal
  portale AI Foundry.

## 1. Infrastruttura

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars          # almeno budget_alert_email

export ARM_SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
terraform init
terraform plan
terraform apply
```

Al primo apply la Container App parte con l'immagine di esempio di Microsoft:
è normale, l'immagine vera arriva al passo successivo.

Cosa viene creato (18 risorse):

| Risorsa | Scopo |
|---|---|
| Resource group | Contiene tutto, così si cancella in un colpo solo |
| User-assigned identity | Identità dell'app, con i ruoli su storage e AI |
| Storage account | Table Storage per i dati, Blob per i CV (se abilitato) |
| Log Analytics workspace | Log di Container Apps, con quota giornaliera |
| Container App Environment | Ambiente Consumption |
| Container App | L'API, da 0 a 1 repliche |
| Static Web App | Il frontend, piano Free |
| Cognitive Account (AIServices) | Azure AI Foundry |
| Cognitive Deployment | Il modello, di default gpt-4o-mini |
| Role assignments ×3 | Table Data, Blob Data, OpenAI User |
| Consumption budget | Avviso via email sulla spesa |

Prendi nota degli output:

```bash
terraform output next_steps
terraform output -raw access_code                      # serve per entrare nell'app
terraform output -raw static_web_app_deployment_token  # secret per il workflow
```

### Stato remoto (consigliato)

Di default lo stato è un file locale. Per tenerlo su Azure:

```bash
./scripts/bootstrap-state.sh
cp backend.tf.example backend.tf
$EDITOR backend.tf                # i valori li stampa lo script
terraform init -migrate-state
```

## 2. Immagine dell'API

```bash
cd backend
IMAGE="ghcr.io/<tuo-utente>/interview-prep-copilot-api:$(git rev-parse --short HEAD)"

docker build -t "$IMAGE" .
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <tuo-utente> --password-stdin
docker push "$IMAGE"

az containerapp update \
  --name "$(terraform -chdir=../terraform output -raw api_container_app_name)" \
  --resource-group "$(terraform -chdir=../terraform output -raw resource_group_name)" \
  --image "$IMAGE"
```

> Con un package GHCR pubblico non serve alcuna credenziale e non serve un
> Azure Container Registry, che costerebbe ~4,60 EUR/mese. Dopo il primo push
> vai su GitHub → Packages → il package → Package settings → Change visibility →
> Public. Se preferisci tenerlo privato, imposta `create_container_registry = true`
> oppure valorizza `registry_username` e `registry_password`.

Verifica:

```bash
API_URL="$(terraform -chdir=../terraform output -raw api_url)"
curl -s "$API_URL/api/health"
curl -s "$API_URL/api/meta" | python3 -m json.tool
```

In `/api/meta` controlla `ai_enabled: true` e `ai_auth: "managed_identity"`.

## 3. Frontend

```bash
cd frontend
VITE_API_BASE_URL="$(terraform -chdir=../terraform output -raw api_url)" npm run build

npx @azure/static-web-apps-cli deploy ./dist \
  --deployment-token "$(terraform -chdir=../terraform output -raw static_web_app_deployment_token)" \
  --env production
```

Apri l'URL che restituisce `terraform output frontend_url` e inserisci il
codice di accesso.

## Deploy automatico con GitHub Actions

I tre workflow in `.github/workflows/` coprono CI e deploy. Per attivarli
servono alcuni secret nell'ambiente `production` del repository.

### Login federato ad Azure (senza password)

```bash
APP_ID=$(az ad app create --display-name "interview-prep-copilot-deploy" --query appId -o tsv)
az ad sp create --id "$APP_ID"
OBJ_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)
RG=$(terraform -chdir=terraform output -raw resource_group_name)
SUB=$(az account show --query id -o tsv)

# Il service principal può agire solo su questo resource group.
az role assignment create \
  --assignee "$APP_ID" \
  --role "Contributor" \
  --scope "/subscriptions/$SUB/resourceGroups/$RG"

# Credenziale federata: GitHub ottiene un token OIDC, nessun segreto da ruotare.
az ad app federated-credential create --id "$OBJ_ID" --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<owner>/<repo>:environment:production",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

> Il `subject` deve corrispondere esattamente a come parte il workflow. I
> workflow di deploy dichiarano `environment: production`, quindi la forma è
> `repo:owner/repo:environment:production`. Se togli l'environment, diventa
> `repo:owner/repo:ref:refs/heads/main`.

### Secret da configurare

| Secret | Da dove si prende |
|---|---|
| `AZURE_CLIENT_ID` | `$APP_ID` qui sopra |
| `AZURE_TENANT_ID` | `az account show --query tenantId -o tsv` |
| `AZURE_SUBSCRIPTION_ID` | `az account show --query id -o tsv` |
| `AZURE_RESOURCE_GROUP` | `terraform output -raw resource_group_name` |
| `AZURE_CONTAINER_APP_NAME` | `terraform output -raw api_container_app_name` |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | `terraform output -raw static_web_app_deployment_token` |
| `API_BASE_URL` | `terraform output -raw api_url` |

Da quel momento un push su `main` che tocca `backend/` ricostruisce e rilascia
l'API, e uno che tocca `frontend/` ripubblica il sito.

## Aggiornare il modello AI

Prima guarda cosa è davvero disponibile nella tua regione:

```powershell
cd terraform
.\scripts\list-models.ps1 -Location swedencentral
```

Poi cambia `ai_model_name`, `ai_model_version` e, per i modelli reasoning,
`ai_api_version` in `terraform.tfvars` e lancia `terraform apply`.

**Non serve ricostruire l'immagine né ripubblicare il frontend**: il deployment
arriva alla Container App come variabile d'ambiente.

La guida completa, con il confronto fra famiglie, dove il modello fa davvero la
differenza e cosa fare quando qualcosa non va, è in
[modelli.md](modelli.md).

## Smontare tutto

```bash
cd terraform && terraform destroy
```

Cancella anche i dati. Se hai argomenti aggiunti che vuoi tenere, esportali
prima da Argomenti → Esporta aggiunti e committali in `backend/app/content/`.
