#!/usr/bin/env bash
# Aggiorna la Container App all'immagine gia' pubblicata su GHCR. Senza Docker.
# Equivalente di scripts/update-api.ps1.
#   ./scripts/update-api.sh [tag]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF="$ROOT/terraform"
TAG="${1:-latest}"

step() { printf '\n=== %s ===\n' "$1"; }
# Gli output aggiunti dopo il primo apply possono non esserci: qui l'assenza
# vale stringa vuota invece di fermare lo script.
tf_out() { terraform -chdir="$TF" output -raw "$1" 2>/dev/null || true; }

command -v az >/dev/null || { echo "  X  Azure CLI non trovata." >&2; exit 1; }
az account show >/dev/null 2>&1 || { echo "  X  Esegui prima: az login" >&2; exit 1; }

RG="$(terraform -chdir="$TF" output -raw resource_group_name)"
APP="$(terraform -chdir="$TF" output -raw api_container_app_name)"
API_URL="$(terraform -chdir="$TF" output -raw api_url)"
WEB_URL="$(terraform -chdir="$TF" output -raw frontend_url)"
CODE="$(tf_out access_code)"
# Vuoti con enable_entra_auth = false.
AUTH_MODE="$(tf_out auth_mode)"
ENTRA_CLIENT_ID="$(tf_out entra_client_id)"

IMAGE="${IMAGE:-}"
if [ -z "$IMAGE" ]; then
  SLUG="$(git -C "$ROOT" remote get-url origin \
    | sed -nE 's#.*github\.com[:/]([^/]+)/([^/.]+)(\.git)?$#\1/\2#p')"
  [ -n "$SLUG" ] || { echo "  X  Imposta IMAGE=<riferimento>." >&2; exit 1; }
  IMAGE="ghcr.io/${SLUG}-api:$TAG"
fi

step "Aggiornamento"
echo "  Container App : $APP"
echo "  Immagine      : $IMAGE"
az containerapp update --name "$APP" --resource-group "$RG" --image "$IMAGE" --output none || {
  echo "  !  Fallito. Il workflow 'Deploy API' e' stato eseguito? Il package e' raggiungibile?" >&2
  exit 1
}

step "Verifica"
printf '  Attendo che l API risponda'
HEALTHY=false
for _ in $(seq 1 30); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/api/health" || true)" = "200" ]; then
    HEALTHY=true; echo " -> OK"; break
  fi
  printf '.'; sleep 10
done

if ! $HEALTHY; then
  echo
  echo "  !  Health check non passato: az containerapp logs show -n $APP -g $RG --tail 50" >&2
  exit 1
fi

# /api/meta resta pubblico anche con il login attivo.
curl -s "$API_URL/api/meta" | head -c 300; echo

# Con Entra ID il codice condiviso non autentica piu' nulla: serve un token
# utente, e la Azure CLI ne ha gia' uno se e' pre-autorizzata sull'app
# registration (entra_allow_azure_cli = true).
if [ "$AUTH_MODE" = "entra_id" ]; then
  TOKEN=""
  if [ -n "$ENTRA_CLIENT_ID" ]; then
    TOKEN="$(az account get-access-token --resource "api://$ENTRA_CLIENT_ID" \
      --query accessToken --output tsv 2>/dev/null || true)"
  fi
  if [ -z "$TOKEN" ]; then
    echo "  !  Selftest saltato: la Azure CLI non ha ottenuto un token per l'API."
    echo "     Metti entra_allow_azure_cli = true in terraform.tfvars e rilancia apply,"
    echo "     oppure verifica dal browser: apri $WEB_URL, fai login e genera un piano."
  else
    curl -s -X POST "$API_URL/api/ai/selftest" -H "Authorization: Bearer $TOKEN" | head -c 600
    echo
  fi
elif [ -n "$CODE" ]; then
  curl -s -X POST "$API_URL/api/ai/selftest" -H "X-Access-Code: $CODE" | head -c 600
  echo
fi

step "Fatto"
echo
echo "  App: $WEB_URL"
echo "  API: $API_URL"
echo
