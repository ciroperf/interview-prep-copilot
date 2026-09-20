# Elenca i modelli di chat davvero deployabili nella tua sottoscrizione e regione.
# Il catalogo cambia nel tempo e per regione: questo e' l'unico modo affidabile
# di sapere cosa puoi usare, invece di fidarsi di una lista scritta a mano.
#
#   .\scripts\list-models.ps1 [-Location swedencentral]
param(
    [string]$Location = "swedencentral"
)

$ErrorActionPreference = "Stop"

# Il catalogo contiene anche modelli che a questa app non servono: embedding,
# sintesi vocale, trascrizione, immagini, video, audio e realtime. Li togliamo,
# altrimenti l'elenco e' lungo il doppio e induce a sceglierne uno sbagliato.
$esclusi = @(
    "!contains(model.name,'embedding')"
    "!contains(model.name,'tts')"
    "!contains(model.name,'whisper')"
    "!contains(model.name,'transcribe')"
    "!contains(model.name,'image')"
    "!contains(model.name,'audio')"
    "!contains(model.name,'realtime')"
    "!contains(model.name,'sora')"
    "!contains(model.name,'live')"
) -join " && "

# Nota: si elencano TUTTE le SKU, non solo la prima. Un modello che offre sia
# Standard sia GlobalStandard mostrerebbe solo Standard, e sceglieresti la SKU
# sbagliata in terraform.tfvars facendo fallire l'apply.
$campi = "modello: model.name, versione: model.version, sku: join(', ', model.skus[].name), capacita_max: max(model.skus[].capacity.maximum)"
$query = "[?kind=='AIServices' && model.format=='OpenAI' && $esclusi].{$campi}"

Write-Host "Modelli di chat disponibili in ${Location}:" -ForegroundColor Cyan
Write-Host ""

az cognitiveservices model list --location $Location --query $query --output table
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nessun risultato. Hai fatto 'az login'? La regione e' valida?" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Per usarne uno, in terraform\terraform.tfvars:" -ForegroundColor Cyan
Write-Host '  ai_model_name     = "<modello>"'
Write-Host '  ai_model_version  = "<versione>"'
Write-Host '  ai_deployment_sku = "<una delle SKU elencate sopra>"'
Write-Host ""
Write-Host "Attenzione alla SKU: se il modello non offre GlobalStandard (il default" -ForegroundColor Yellow
Write-Host "del Terraform) devi indicare quella giusta, altrimenti l'apply fallisce." -ForegroundColor Yellow
Write-Host ""
Write-Host "I modelli reasoning (o1, o3, o4, gpt-5 e successivi) richiedono anche:" -ForegroundColor Yellow
Write-Host '  ai_api_version = "2025-01-01-preview"   (o una preview piu'' recente)'
Write-Host ""
Write-Host "Guida alla scelta: docs/modelli.md"
Write-Host "Poi: terraform apply"
