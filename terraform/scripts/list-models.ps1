# Elenca i modelli chat davvero deployabili nella tua sottoscrizione e regione.
# Il catalogo cambia nel tempo e per regione: questo e' l'unico modo affidabile
# di sapere cosa puoi usare, invece di fidarsi di una lista scritta a mano.
#
#   .\scripts\list-models.ps1 [-Location swedencentral]
param(
    [string]$Location = "swedencentral"
)

$ErrorActionPreference = "Stop"

Write-Host "Modelli chat disponibili in ${Location}:" -ForegroundColor Cyan
Write-Host ""

$query = "[?kind=='AIServices' && model.format=='OpenAI'].{modello: model.name, versione: model.version, sku: model.skus[0].name, capacita_max: model.skus[0].capacity.maximum}"

az cognitiveservices model list --location $Location --query $query --output table

Write-Host ""
Write-Host "Per usarne uno, in terraform\terraform.tfvars:" -ForegroundColor Cyan
Write-Host '  ai_model_name    = "<modello>"'
Write-Host '  ai_model_version = "<versione>"'
Write-Host ""
Write-Host "I modelli o3, o4-mini e gpt-5 sono reasoning: richiedono anche" -ForegroundColor Yellow
Write-Host '  ai_api_version = "2025-01-01-preview"   (o una preview piu recente)'
Write-Host ""
Write-Host "Poi: terraform apply"
