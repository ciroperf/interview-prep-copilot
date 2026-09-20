#!/usr/bin/env bash
# Aggiorna la Container App all'immagine gia' pubblicata su GHCR. Senza Docker.
# Equivalente di scripts/update-api.ps1.
#   ./scripts/update-api.sh [tag]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF="$ROOT/terraform"
TAG="${1:-latest}"

step() { printf '\n=== %s ===\n' "$1"; }

command -v az >/dev/null || { echo "  X  Azure CLI non trovata." >&2; exit 1; }
az account show >/dev/null 2>&1 || { echo "  X  Esegui prima: az login" >&2; exit 1; }

RG="$(terraform -chdir="$TF" output -raw resource_group_name)"
APP="$(terraform -chdir="$TF" output -raw api_container_app_name)"
API_URL="$(terraform -chdir="$TF" output -raw api_url)"
CODE="$(terraform -chdir="$TF" output -raw access_code)"

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
for _ in $(seq 1 30); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/api/health" || true)" = "200" ]; then
    echo " -> OK"
    curl -s -X POST "$API_URL/api/ai/selftest" -H "X-Access-Code: $CODE" | head -c 600
    echo
    exit 0
  fi
  printf '.'; sleep 10
done
echo
echo "  !  Health check non passato: az containerapp logs show -n $APP -g $RG --tail 50" >&2
exit 1
