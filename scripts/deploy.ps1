<#
.SYNOPSIS
    Deploy completo di Interview Prep Copilot su Azure, da Windows.

.DESCRIPTION
    Esegue in ordine: infrastruttura con Terraform, immagine dell'API, bundle
    del frontend. Puo' essere rilanciato: Terraform e' idempotente e i passi
    successivi aggiornano quello che c'e'.

.PARAMETER SkipInfra
    Salta Terraform. Utile quando cambi solo il codice.

.PARAMETER SkipApi
    Salta build e push dell'immagine dell'API.

.PARAMETER SkipWeb
    Salta build e pubblicazione del frontend.

.PARAMETER GitHubUser
    Utente o organizzazione GitHub per il package su GHCR. Se omesso viene
    dedotto dal remote git.

.EXAMPLE
    .\scripts\deploy.ps1
    .\scripts\deploy.ps1 -SkipInfra          # solo codice, infrastruttura invariata
#>
[CmdletBinding()]
param(
    [switch]$SkipInfra,
    [switch]$SkipApi,
    [switch]$SkipWeb,
    [string]$GitHubUser = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tf = Join-Path $root "terraform"

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "  OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  !   $text" -ForegroundColor Yellow }
function Fail($text) { Write-Host "  X   $text" -ForegroundColor Red; exit 1 }

function Require($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Fail "$cmd non trovato. $hint"
    }
    Ok "$cmd presente"
}

# ---------------------------------------------------------------------------
Step "Prerequisiti"

Require "az" "Installa la Azure CLI: winget install Microsoft.AzureCLI"
if (-not $SkipInfra) { Require "terraform" "Installa Terraform: winget install HashiCorp.Terraform" }
if (-not $SkipWeb)   { Require "node" "Installa Node.js 22: winget install OpenJS.NodeJS.LTS" }

$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) { Fail "Non sei autenticato. Esegui: az login" }
Ok "Sottoscrizione: $($account.name)"
$env:ARM_SUBSCRIPTION_ID = $account.id

# Senza Docker l'immagine la costruisce GitHub Actions: qui ci limitiamo a
# portare in Azure quella gia' pubblicata su GHCR, con la sola az CLI.
$hasDocker = [bool](Get-Command docker -ErrorAction SilentlyContinue)
$useGitHubBuild = (-not $SkipApi) -and (-not $hasDocker)
if ($useGitHubBuild) {
    Ok "Docker assente: usero' l'immagine costruita da GitHub Actions"
}

if (-not $GitHubUser) {
    $remote = git -C $root remote get-url origin 2>$null
    if ($remote -match "github\.com[:/]([^/]+)/") { $GitHubUser = $Matches[1] }
}

# ---------------------------------------------------------------------------
if (-not $SkipInfra) {
    Step "Infrastruttura (Terraform)"

    $tfvars = Join-Path $tf "terraform.tfvars"
    if (-not (Test-Path $tfvars)) {
        Copy-Item (Join-Path $tf "terraform.tfvars.example") $tfvars
        Warn "Creato terraform.tfvars dal template."
        Warn "Aprilo e compila almeno budget_alert_email, poi rilancia."
        notepad $tfvars
        exit 0
    }

    Push-Location $tf
    try {
        terraform init -input=false
        if ($LASTEXITCODE -ne 0) { Fail "terraform init fallito" }

        terraform apply -input=false
        if ($LASTEXITCODE -ne 0) { Fail "terraform apply fallito" }
        Ok "Infrastruttura allineata"
    } finally { Pop-Location }
}

# Gli output servono a tutti i passi successivi.
Push-Location $tf
try {
    $rg      = terraform output -raw resource_group_name
    $appName = terraform output -raw api_container_app_name
    $apiUrl  = terraform output -raw api_url
    $webUrl  = terraform output -raw frontend_url
    $swaName = terraform output -raw static_web_app_name
    $code    = terraform output -raw access_code
    $swaToken = terraform output -raw static_web_app_deployment_token
} catch {
    Fail "Non riesco a leggere gli output di Terraform. Hai gia' fatto un apply?"
} finally { Pop-Location }

# ---------------------------------------------------------------------------
if ($useGitHubBuild) {
    Step "Immagine dell'API (costruita da GitHub Actions)"

    if (-not $GitHubUser) { Fail "Non riesco a dedurre l'utente GitHub. Usa -GitHubUser <nome>." }
    $repoName = ""
    $remote = git -C $root remote get-url origin 2>$null
    if ($remote -match "github\.com[:/][^/]+/([^/.]+)") { $repoName = $Matches[1] }

    Write-Host "  Il workflow 'Deploy API' costruisce e pubblica su GHCR."
    Write-Host "  Controlla che sia finito: https://github.com/$GitHubUser/$repoName/actions"
    Write-Host ""
    $risposta = Read-Host "  Il workflow e' terminato con successo? [s/N]"
    if ($risposta -notmatch '^[sSyY]') {
        Warn "Salto l'aggiornamento dell'API."
        Warn "Quando il workflow e' finito, lancia: .\scripts\update-api.ps1"
        $SkipApi = $true
    } else {
        & (Join-Path $PSScriptRoot "update-api.ps1")
        if ($LASTEXITCODE -ne 0) { Fail "Aggiornamento dell'API non riuscito" }
        $SkipApi = $true   # gia' fatto, salta il ramo con Docker
    }
}

if (-not $SkipApi) {
    Step "Immagine dell'API (build locale con Docker)"

    if (-not $GitHubUser) { Fail "Non riesco a dedurre l'utente GitHub. Usa -GitHubUser <nome>." }

    $sha = (git -C $root rev-parse --short HEAD).Trim()
    $image = "ghcr.io/$GitHubUser/interview-prep-copilot-api"
    Write-Host "  Immagine: ${image}:$sha"

    docker build -t "${image}:$sha" -t "${image}:latest" (Join-Path $root "backend")
    if ($LASTEXITCODE -ne 0) { Fail "docker build fallito" }

    if (-not $env:GITHUB_TOKEN) {
        Warn "GITHUB_TOKEN non impostato: serve un token con scope write:packages."
        Warn 'Creane uno su https://github.com/settings/tokens poi: $env:GITHUB_TOKEN="ghp_..."'
        Fail "Push su GHCR impossibile"
    }
    $env:GITHUB_TOKEN | docker login ghcr.io -u $GitHubUser --password-stdin
    if ($LASTEXITCODE -ne 0) { Fail "docker login fallito" }

    docker push "${image}:$sha"
    docker push "${image}:latest"
    if ($LASTEXITCODE -ne 0) { Fail "docker push fallito" }

    az containerapp update --name $appName --resource-group $rg --image "${image}:$sha" --output none
    if ($LASTEXITCODE -ne 0) { Fail "aggiornamento della Container App fallito" }
    Ok "Container App aggiornata"

    Write-Host "  Attendo che l'API risponda..." -NoNewline
    $healthy = $false
    foreach ($i in 1..30) {
        try {
            $r = Invoke-WebRequest "$apiUrl/api/health" -UseBasicParsing -TimeoutSec 10
            if ($r.StatusCode -eq 200) { $healthy = $true; break }
        } catch { }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 10
    }
    Write-Host ""
    if (-not $healthy) {
        Warn "L'health check non e' passato. Log: az containerapp logs show -n $appName -g $rg --tail 50"
    } else {
        Ok "API viva"
        $meta = Invoke-RestMethod "$apiUrl/api/meta"
        Write-Host "      AI: $(if ($meta.ai_enabled) { "$($meta.ai_deployment) [$($meta.ai_family)]" } else { 'non attiva' })"
        Write-Host "      Catalogo: $($meta.content.topics) argomenti, $($meta.content.questions) domande"
    }
}

# ---------------------------------------------------------------------------
if (-not $SkipWeb) {
    Step "Frontend"

    Push-Location (Join-Path $root "frontend")
    try {
        if (-not (Test-Path "node_modules")) { npm ci }
        $env:VITE_API_BASE_URL = $apiUrl
        npm run build
        if ($LASTEXITCODE -ne 0) { Fail "build del frontend fallita" }
        Ok "Bundle compilato con API = $apiUrl"

        npx --yes @azure/static-web-apps-cli deploy ./dist --deployment-token $swaToken --env production
        if ($LASTEXITCODE -ne 0) { Fail "pubblicazione sulla Static Web App fallita" }
        Ok "Frontend pubblicato"
    } finally { Pop-Location }
}

# ---------------------------------------------------------------------------
Step "Fatto"

Write-Host ""
Write-Host "  App           : $webUrl" -ForegroundColor Green
Write-Host "  API           : $apiUrl"
Write-Host "  Codice accesso: $code" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Il codice di accesso e' anche recuperabile con:"
Write-Host "    terraform -chdir=terraform output -raw access_code"
Write-Host ""
Write-Host "  Per verificare che il modello AI risponda davvero:"
Write-Host "    .\scripts\update-api.ps1      (aggiorna e lancia il selftest)"
Write-Host ""
