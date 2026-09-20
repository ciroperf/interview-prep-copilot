<#
.SYNOPSIS
    Aggiorna la Container App all'immagine gia' pubblicata su GHCR. Senza Docker.

.DESCRIPTION
    L'immagine la costruisce GitHub Actions (workflow "Deploy API"); questo
    script la porta in Azure usando la sola Azure CLI. E' il percorso per chi
    non vuole installare Docker in locale.

    Dopo l'aggiornamento attende che l'API risponda e lancia il selftest
    dell'AI, cosi' sai subito se modello e permessi sono a posto.

.PARAMETER Tag
    Tag dell'immagine. Default "latest". Per fissare una revisione a un commit
    preciso passa il SHA completo che vedi nel riepilogo del workflow.

.PARAMETER Image
    Riferimento completo dell'immagine, se vuoi scavalcare la deduzione
    automatica dal remote git.

.EXAMPLE
    .\scripts\update-api.ps1
    .\scripts\update-api.ps1 -Tag 9fceb02d1c2f3e4a5b6c7d8e9f0a1b2c3d4e5f60
#>
[CmdletBinding()]
param(
    [string]$Tag = "latest",
    [string]$Image = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tf = Join-Path $root "terraform"

function Step($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  !   $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host "  X   $t" -ForegroundColor Red; exit 1 }

Step "Prerequisiti"
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    # winget scrive il PATH nel registro ma la sessione aperta ha quello vecchio.
    $machine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = @($machine, $user | Where-Object { $_ }) -join ';'
}
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Fail "Azure CLI non trovata. winget install Microsoft.AzureCLI, poi riapri PowerShell."
}
if (-not (az account show --output json 2>$null)) { Fail "Esegui prima: az login" }
Ok "Azure CLI pronta"

# Gli output di Terraform sono la fonte dei nomi: niente da copiare a mano.
Push-Location $tf
try {
    $rg      = terraform output -raw resource_group_name
    $appName = terraform output -raw api_container_app_name
    $apiUrl  = terraform output -raw api_url
    $code    = terraform output -raw access_code
} catch {
    Fail "Non riesco a leggere gli output di Terraform. Hai gia' fatto terraform apply?"
} finally { Pop-Location }

if (-not $Image) {
    $remote = git -C $root remote get-url origin 2>$null
    if ($remote -notmatch "github\.com[:/]([^/]+)/([^/.]+)") {
        Fail "Non riesco a dedurre il repository dal remote git. Usa -Image <riferimento>."
    }
    $Image = "ghcr.io/$($Matches[1])/$($Matches[2])-api:$Tag"
}

Step "Aggiornamento"
Write-Host "  Container App : $appName"
Write-Host "  Immagine      : $Image"

az containerapp update --name $appName --resource-group $rg --image $Image --output none
if ($LASTEXITCODE -ne 0) {
    Warn "Aggiornamento fallito. Cause tipiche:"
    Warn "  - il workflow 'Deploy API' non e' ancora stato eseguito su GitHub"
    Warn "  - il package GHCR e' privato e la Container App non ha le credenziali"
    Warn "    (vedi registry_username / registry_password in terraform.tfvars)"
    Fail "Controlla e riprova"
}
Ok "Revisione creata"

Step "Verifica"
Write-Host "  Attendo che l'API risponda" -NoNewline
$healthy = $false
foreach ($i in 1..30) {
    try {
        if ((Invoke-WebRequest "$apiUrl/api/health" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200) {
            $healthy = $true; break
        }
    } catch { }
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 10
}
Write-Host ""

if (-not $healthy) {
    Warn "L'health check non e' passato. Guarda i log:"
    Warn "  az containerapp logs show -n $appName -g $rg --tail 50"
    exit 1
}
Ok "API viva"

$meta = Invoke-RestMethod "$apiUrl/api/meta"
Write-Host "      Catalogo: $($meta.content.topics) argomenti, $($meta.content.questions) domande, $($meta.content.problems) problemi"

if (-not $meta.ai_enabled) {
    Warn "AI non attiva su questa istanza (enable_ai = false)."
} else {
    Write-Host "      Modello : $($meta.ai_deployment) [$($meta.ai_family)]"
    Write-Host "  Provo una generazione vera..."
    try {
        $test = Invoke-RestMethod "$apiUrl/api/ai/selftest" -Method Post -Headers @{ "X-Access-Code" = $code }
        if ($test.ok) {
            Ok "AI funzionante ($($test.latency_ms) ms, api-version $($test.api_version_used))"
            if ($test.adapted) { Warn $test.hint }
        } else {
            Warn "L'AI risponde con un errore: $($test.error)"
            Warn "Suggerimento: $($test.hint)"
        }
    } catch {
        Warn "Selftest non riuscito: $_"
    }
}

Step "Fatto"
Write-Host ""
Write-Host "  App: $(terraform -chdir=$tf output -raw frontend_url)" -ForegroundColor Green
Write-Host "  API: $apiUrl"
Write-Host ""
