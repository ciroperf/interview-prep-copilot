#!/usr/bin/env bash
# Deploy completo su Azure. Equivalente di scripts/deploy.ps1.
#   ./scripts/deploy.sh [--skip-infra] [--skip-api] [--skip-web]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF="$ROOT/terraform"
SKIP_INFRA=false; SKIP_API=false; SKIP_WEB=false

for arg in "$@"; do
  case "$arg" in
    --skip-infra) SKIP_INFRA=true ;;
    --skip-api)   SKIP_API=true ;;
    --skip-web)   SKIP_WEB=true ;;
    *) echo "Argomento sconosciuto: $arg" >&2; exit 1 ;;
  esac
done

step() { printf '\n=== %s ===\n' "$1"; }
need() { command -v "$1" >/dev/null || { echo "  X  $1 non trovato. $2" >&2; exit 1; }; }

step "Prerequisiti"
need az "Installa la Azure CLI."
$SKIP_INFRA || need terraform "Installa Terraform."
$SKIP_WEB || need node "Installa Node.js 22."
az account show >/dev/null 2>&1 || { echo "  X  Esegui: az login" >&2; exit 1; }
ARM_SUBSCRIPTION_ID="$(az account show --query id -o tsv)"; export ARM_SUBSCRIPTION_ID
echo "  OK  sottoscrizione $(az account show --query name -o tsv)"

USE_GITHUB_BUILD=false
if ! $SKIP_API && ! command -v docker >/dev/null; then
  # Senza Docker l'immagine la costruisce GitHub Actions: qui la portiamo in
  # Azure con la sola az CLI.
  echo "  OK  Docker assente: usero' l'immagine costruita da GitHub Actions"
  USE_GITHUB_BUILD=true
  SKIP_API=true
fi

GITHUB_USER="${GITHUB_USER:-$(git -C "$ROOT" remote get-url origin 2>/dev/null \
  | sed -nE 's#.*github\.com[:/]([^/]+)/.*#\1#p')}"

if ! $SKIP_INFRA; then
  step "Infrastruttura (Terraform)"
  if [ ! -f "$TF/terraform.tfvars" ]; then
    cp "$TF/terraform.tfvars.example" "$TF/terraform.tfvars"
    echo "  !   Creato terraform.tfvars: compilalo e rilancia."
    exit 0
  fi
  terraform -chdir="$TF" init -input=false
  terraform -chdir="$TF" apply -input=false
fi

RG="$(terraform -chdir="$TF" output -raw resource_group_name)"
APP="$(terraform -chdir="$TF" output -raw api_container_app_name)"
API_URL="$(terraform -chdir="$TF" output -raw api_url)"
WEB_URL="$(terraform -chdir="$TF" output -raw frontend_url)"
CODE="$(terraform -chdir="$TF" output -raw access_code)"
SWA_TOKEN="$(terraform -chdir="$TF" output -raw static_web_app_deployment_token)"
# Vuoti quando enable_entra_auth = false.
ENTRA_CLIENT_ID="$(terraform -chdir="$TF" output -raw entra_client_id)"
ENTRA_TENANT_ID="$(terraform -chdir="$TF" output -raw entra_tenant_id)"
ENTRA_API_SCOPE="$(terraform -chdir="$TF" output -raw entra_api_scope)"
AUTH_MODE="$(terraform -chdir="$TF" output -raw auth_mode)"

if ! $SKIP_API; then
  step "Immagine dell'API"
  [ -n "$GITHUB_USER" ] || { echo "  X  Imposta GITHUB_USER." >&2; exit 1; }
  SHA="$(git -C "$ROOT" rev-parse --short HEAD)"
  IMAGE="ghcr.io/$GITHUB_USER/interview-prep-copilot-api"

  docker build -t "$IMAGE:$SHA" -t "$IMAGE:latest" "$ROOT/backend"
  [ -n "${GITHUB_TOKEN:-}" ] || { echo "  X  Imposta GITHUB_TOKEN (scope write:packages)." >&2; exit 1; }
  echo "$GITHUB_TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin
  docker push "$IMAGE:$SHA"
  docker push "$IMAGE:latest"

  az containerapp update --name "$APP" --resource-group "$RG" --image "$IMAGE:$SHA" --output none
  printf '  Attendo che l API risponda'
  for _ in $(seq 1 30); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/api/health" || true)" = "200" ]; then
      echo " -> OK"; curl -s "$API_URL/api/meta" | head -c 300; echo; break
    fi
    printf '.'; sleep 10
  done
fi

if ! $SKIP_WEB; then
  step "Frontend"
  cd "$ROOT/frontend"
  [ -d node_modules ] || npm ci
  VITE_API_BASE_URL="$API_URL" \
  VITE_ENTRA_CLIENT_ID="$ENTRA_CLIENT_ID" \
  VITE_ENTRA_TENANT_ID="$ENTRA_TENANT_ID" \
  VITE_ENTRA_API_SCOPE="$ENTRA_API_SCOPE" \
    npm run build
  npx --yes @azure/static-web-apps-cli deploy ./dist --deployment-token "$SWA_TOKEN" --env production
fi

if $USE_GITHUB_BUILD; then
  step "Immagine dell API"
  echo "  Quando il workflow 'Deploy API' e' terminato, lancia:"
  echo "    ./scripts/update-api.sh"
fi

step "Fatto"
cat <<MSG

  App           : $WEB_URL
  API           : $API_URL
  Accesso       : $AUTH_MODE
  Codice accesso: $CODE   (ignorato con il login Microsoft)

MSG
