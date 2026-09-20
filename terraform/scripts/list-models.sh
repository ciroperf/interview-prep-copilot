#!/usr/bin/env bash
# Elenca i modelli chat davvero deployabili nella tua sottoscrizione e regione.
# Il catalogo cambia nel tempo e per regione: questo è l'unico modo affidabile
# di sapere cosa puoi usare, invece di fidarsi di una lista scritta a mano.
#
#   ./scripts/list-models.sh [regione]
set -euo pipefail

LOCATION="${1:-${LOCATION:-swedencentral}}"

echo "Modelli chat disponibili in $LOCATION:"
echo

az cognitiveservices model list \
  --location "$LOCATION" \
  --query "[?kind=='AIServices' && model.format=='OpenAI'].{
             modello: model.name,
             versione: model.version,
             sku: model.skus[0].name,
             capacita_max: model.skus[0].capacity.maximum
           }" \
  --output table 2>/dev/null \
  | sort \
  || {
    echo "Nessun risultato. Controlla di aver fatto 'az login' e che la regione sia valida." >&2
    exit 1
  }

cat <<'MSG'

Per usarne uno, in terraform/terraform.tfvars:

  ai_model_name    = "<modello>"
  ai_model_version = "<versione>"

I modelli o3, o4-mini e gpt-5 sono reasoning: richiedono anche
  ai_api_version = "2025-01-01-preview"   (o una preview più recente)

Poi: terraform apply
MSG
