#!/usr/bin/env bash
# Elenca i modelli di chat davvero deployabili nella tua sottoscrizione e regione.
# Il catalogo cambia nel tempo e per regione: questo è l'unico modo affidabile
# di sapere cosa puoi usare, invece di fidarsi di una lista scritta a mano.
#
#   ./scripts/list-models.sh [regione]
set -euo pipefail

LOCATION="${1:-${LOCATION:-swedencentral}}"

# Il catalogo contiene anche modelli che a questa app non servono: embedding,
# sintesi vocale, trascrizione, immagini, video, audio e realtime. Li togliamo,
# altrimenti l'elenco è lungo il doppio e induce a sceglierne uno sbagliato.
ESCLUSI="!contains(model.name,'embedding') \
&& !contains(model.name,'tts') \
&& !contains(model.name,'whisper') \
&& !contains(model.name,'transcribe') \
&& !contains(model.name,'image') \
&& !contains(model.name,'audio') \
&& !contains(model.name,'realtime') \
&& !contains(model.name,'sora') \
&& !contains(model.name,'live')"

# Nota: si elencano TUTTE le SKU, non solo la prima. Un modello che offre sia
# Standard sia GlobalStandard mostrerebbe solo Standard, e sceglieresti la SKU
# sbagliata in terraform.tfvars facendo fallire l'apply.
echo "Modelli di chat disponibili in $LOCATION:"
echo

az cognitiveservices model list \
  --location "$LOCATION" \
  --query "[?kind=='AIServices' && model.format=='OpenAI' && ${ESCLUSI}].{
             modello: model.name,
             versione: model.version,
             sku: join(', ', model.skus[].name),
             capacita_max: max(model.skus[].capacity.maximum)
           }" \
  --output table 2>/dev/null \
  || {
    echo "Nessun risultato. Controlla di aver fatto 'az login' e che la regione sia valida." >&2
    exit 1
  }

cat <<'MSG'

Per usarne uno, in terraform/terraform.tfvars:

  ai_model_name     = "<modello>"
  ai_model_version  = "<versione>"
  ai_deployment_sku = "<una delle SKU elencate sopra>"

Attenzione alla SKU: se il modello non offre GlobalStandard (il default del
Terraform) devi indicare quella giusta, altrimenti l'apply fallisce.

I modelli reasoning (o1, o3, o4, gpt-5 e successivi) richiedono anche:
  ai_api_version = "2025-01-01-preview"   (o una preview più recente)

Guida alla scelta: docs/modelli.md
Poi: terraform apply
MSG
