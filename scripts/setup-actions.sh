#!/usr/bin/env bash
# Configura il deploy automatico da GitHub Actions. Da lanciare una volta sola.
#
# Equivalente di scripts/setup-actions.ps1 per macOS e Linux. Fa tutto quello
# che docs/deploy.md descrive a mano: app registration, ruolo sul solo resource
# group, credenziale federata e segreti nell'ambiente "production".
#
# E' idempotente e non stampa nessun valore segreto.
#
#   az login && gh auth login
#   ./scripts/setup-actions.sh
set -euo pipefail

APP_NAME="${APP_NAME:-interview-prep-copilot-deploy}"
ENVIRONMENT="${ENVIRONMENT:-production}"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tf="$root/terraform"

step() { printf '\n\033[36m=== %s ===\033[0m\n' "$1"; }
ok()   { printf '\033[32m  OK  %s\033[0m\n' "$1"; }
warn() { printf '\033[33m  !   %s\033[0m\n' "$1"; }
fail() { printf '\033[31m  X   %s\033[0m\n' "$1"; exit 1; }

# --- prerequisiti ----------------------------------------------------------

step "Prerequisiti"
command -v az        >/dev/null || fail "az non trovato: https://aka.ms/installazurecli"
command -v gh        >/dev/null || fail "gh non trovato: https://cli.github.com"
command -v terraform >/dev/null || fail "terraform non trovato: https://developer.hashicorp.com/terraform/install"
ok "az, gh e terraform disponibili"

az account show >/dev/null 2>&1 || fail "Non sei autenticato su Azure. Lancia: az login"
SUB_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
ok "Azure: $(az account show --query name -o tsv)"

gh auth status >/dev/null 2>&1 || fail "Non sei autenticato su GitHub. Lancia: gh auth login"
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
[ -n "$REPO" ] || fail "Non riesco a dedurre il repository da questa cartella"
ok "GitHub: $REPO"

# --- output di Terraform ---------------------------------------------------

step "Lettura degli output di Terraform"
tf_out() {
    local valore
    if ! valore=$(terraform -chdir="$tf" output -raw "$1" 2>/dev/null); then
        if [ "${2:-}" = "opzionale" ]; then printf ''; return 0; fi
        fail "Output '$1' non disponibile. Hai gia' lanciato scripts/deploy.sh?"
    fi
    printf '%s' "$valore"
}

RG=$(tf_out resource_group_name)
CONTAINER_APP=$(tf_out api_container_app_name)
API_URL=$(tf_out api_url)
SWA_TOKEN=$(tf_out static_web_app_deployment_token)
AUTH_MODE=$(tf_out auth_mode opzionale)
ENTRA_ID=$(tf_out entra_client_id opzionale)
ENTRA_TEN=$(tf_out entra_tenant_id opzionale)
ENTRA_SCOPE=$(tf_out entra_api_scope opzionale)
ok "Resource group: $RG"
ok "Container App: $CONTAINER_APP"

# --- app registration e federazione ---------------------------------------

step "App registration per il login federato"
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv 2>/dev/null || true)
if [ -z "$APP_ID" ]; then
    APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv) \
        || fail "Creazione dell'app registration fallita. Serve il permesso di crearne nel tenant."
    ok "App registration creata"
else
    ok "App registration gia' esistente, la riuso"
fi

if az ad sp show --id "$APP_ID" >/dev/null 2>&1; then
    ok "Service principal gia' presente"
else
    az ad sp create --id "$APP_ID" --output none || fail "Creazione del service principal fallita"
    ok "Service principal creato"
fi

# Il ruolo e' limitato al resource group del progetto: un principale con
# accesso all'intera sottoscrizione e' un rischio inutile.
SCOPE="/subscriptions/$SUB_ID/resourceGroups/$RG"
if [ -z "$(az role assignment list --assignee "$APP_ID" --scope "$SCOPE" --role Contributor --query "[0].id" -o tsv 2>/dev/null || true)" ]; then
    az role assignment create --assignee "$APP_ID" --role Contributor --scope "$SCOPE" --output none \
        || fail "Assegnazione del ruolo fallita"
    ok "Ruolo Contributor assegnato sul solo resource group"
else
    ok "Ruolo gia' assegnato"
fi

OBJ_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)

# GitHub ha due formati di subject e un repository ne usa uno solo, ma quale
# dipende da quando e' stato creato: dal 15 luglio 2026 i nuovi repository -
# e quelli rinominati o trasferiti dopo quella data - presentano il formato
# "immutabile", che accanto ai nomi porta gli ID numerici di proprietario e
# repository. I nomi si possono riciclare, gli ID no, ed e' il motivo del
# cambio. Creiamo entrambe le credenziali: costano nulla, e cosi' lo script
# funziona senza sapere in che regime sta il repository - e continua a
# funzionare se il repository ci passa domani.
OWNER_ID=$(gh api "repos/$REPO" --jq .owner.id) || fail "Non riesco a leggere l'ID del proprietario"
REPO_ID=$(gh api "repos/$REPO" --jq .id)        || fail "Non riesco a leggere l'ID del repository"
OWNER_NAME="${REPO%%/*}"
REPO_NAME="${REPO##*/}"

NOMI_CRED=("github-${ENVIRONMENT}" "github-${ENVIRONMENT}-immutable")
SUBJECTS=("repo:${REPO}:environment:${ENVIRONMENT}"
          "repo:${OWNER_NAME}@${OWNER_ID}/${REPO_NAME}@${REPO_ID}:environment:${ENVIRONMENT}")

for i in "${!NOMI_CRED[@]}"; do
    nome_cred="${NOMI_CRED[$i]}"; subject="${SUBJECTS[$i]}"
    if [ -n "$(az ad app federated-credential list --id "$OBJ_ID" --query "[?subject=='$subject'] | [0].id" -o tsv 2>/dev/null || true)" ]; then
        ok "Credenziale '$nome_cred' gia' presente"
        continue
    fi
    # Il JSON passa da un file: sulla riga di comando le virgolette si
    # comportano in modo diverso fra le shell e si rompono facilmente.
    tmp=$(mktemp)
    cat > "$tmp" <<JSON
{
  "name": "${nome_cred}",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "${subject}",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON
    az ad app federated-credential create --id "$OBJ_ID" --parameters "@$tmp" --output none \
        || { rm -f "$tmp"; fail "Creazione della credenziale '$nome_cred' fallita"; }
    rm -f "$tmp"
    ok "Credenziale '$nome_cred' creata per $subject"
done

# --- segreti ---------------------------------------------------------------

step "Segreti nell'ambiente '$ENVIRONMENT'"
NOMI=(AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID AZURE_RESOURCE_GROUP
      AZURE_CONTAINER_APP_NAME AZURE_STATIC_WEB_APPS_API_TOKEN API_BASE_URL)
VALORI=("$APP_ID" "$TENANT_ID" "$SUB_ID" "$RG" "$CONTAINER_APP" "$SWA_TOKEN" "$API_URL")

if [ "$AUTH_MODE" = "entra_id" ]; then
    NOMI+=(ENTRA_CLIENT_ID ENTRA_TENANT_ID ENTRA_API_SCOPE)
    VALORI+=("$ENTRA_ID" "$ENTRA_TEN" "$ENTRA_SCOPE")
    ok "Login Microsoft attivo: aggiungo anche i tre segreti ENTRA_*"
else
    warn "auth_mode = '$AUTH_MODE': salto i segreti ENTRA_* (si entra con il codice)"
fi

for i in "${!NOMI[@]}"; do
    nome="${NOMI[$i]}"; valore="${VALORI[$i]}"
    if [ -z "$valore" ]; then warn "$nome : valore vuoto, lo salto"; continue; fi
    # Senza --body, gh legge il valore dallo standard input: cosi' non finisce
    # ne' nella riga di comando ne' nella cronologia della shell.
    printf '%s' "$valore" | gh secret set "$nome" --env "$ENVIRONMENT" --repo "$REPO" >/dev/null \
        || fail "Impossibile scrivere il segreto $nome"
    ok "$nome = ***"
done

step "Fatto"
cat <<TESTO
  Il deploy automatico e' attivo.

    push su main che tocca backend/   ->  ricostruisce e rilascia l'API
    push su main che tocca frontend/  ->  ripubblica il sito

  Per pubblicare subito quello che c'e' gia' su main, senza aspettare un push:

    gh workflow run deploy-backend.yml
    gh workflow run deploy-frontend.yml
    gh run watch

  L'ambiente '$ENVIRONMENT' potrebbe avere una regola di approvazione: se il
  job resta in attesa, approvalo dalla pagina Actions del repository.
TESTO
