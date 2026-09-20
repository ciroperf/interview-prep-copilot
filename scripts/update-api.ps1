<#
.SYNOPSIS
    Aggiorna la Container App all'immagine gia' pubblicata su GHCR. Senza Docker.

.DESCRIPTION
    L'immagine la costruisce GitHub Actions (workflow "Deploy API"); questo
    script la porta in Azure usando la sola Azure CLI. E' il percorso per chi
    non vuole installare Docker in locale.

    Dopo l'aggiornamento attende che l'API risponda e lancia il selftest
    dell'AI, cosi' sai subito se modello e permessi sono a posto. Con il login
    Microsoft attivo il token per il selftest lo chiede alla Azure CLI, che e'
    gia' autenticata come te.

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
# Il controllo degli errori qui si basa su $LASTEXITCODE: senza questa riga,
# nelle versioni di PowerShell che lo prevedono, un comando esterno uscito con
# codice diverso da zero lancerebbe un'eccezione prima del nostro controllo.
$PSNativeCommandUseErrorActionPreference = $false
$root = Split-Path -Parent $PSScriptRoot
$tf = Join-Path $root "terraform"

function Step($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  !   $t" -ForegroundColor Yellow }
function Fail($t) { Write-Host "  X   $t" -ForegroundColor Red; exit 1 }

# Legge un output di Terraform. Quelli aggiunti dopo il primo apply possono non
# esserci ancora: -Optional li lascia vuoti invece di fermare tutto.
function Get-TfOutput([string]$Name, [switch]$Optional) {
    $value = terraform output -raw $Name 2>$null
    if ($LASTEXITCODE -ne 0) {
        if ($Optional) { return "" }
        Fail "Output '$Name' non disponibile. Hai gia' fatto terraform apply?"
    }
    return "$value".Trim()
}

Step "Prerequisiti"
function Test-Strumento($nome) { [bool](Get-Command $nome -ErrorAction SilentlyContinue) }

if (-not (Test-Strumento az) -or -not (Test-Strumento terraform)) {
    # winget scrive il PATH nel registro ma la sessione aperta ha quello vecchio.
    $machine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = @($machine, $user | Where-Object { $_ }) -join ';'
}
if (-not (Test-Strumento az)) {
    Fail "Azure CLI non trovata. winget install Microsoft.AzureCLI, poi riapri PowerShell."
}
if (-not (Test-Strumento terraform)) {
    Fail "Terraform non trovato. winget install HashiCorp.Terraform, poi riapri PowerShell."
}
if (-not (az account show --output json 2>$null)) { Fail "Esegui prima: az login" }
Ok "Azure CLI pronta"

# Gli output di Terraform sono la fonte dei nomi: niente da copiare a mano.
# Si leggono tutti qui, dentro un solo Push-Location: piu' avanti "terraform"
# verrebbe eseguito nella directory sbagliata.
Push-Location $tf
try {
    $rg      = Get-TfOutput resource_group_name
    $appName = Get-TfOutput api_container_app_name
    $apiUrl  = Get-TfOutput api_url
    $webUrl  = Get-TfOutput frontend_url
    $code    = Get-TfOutput access_code -Optional
    # Vuoti quando enable_entra_auth = false.
    $authMode      = Get-TfOutput auth_mode -Optional
    $entraClientId = Get-TfOutput entra_client_id -Optional
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

# /api/health e /api/meta restano pubblici anche con il login attivo: sono gli
# unici due percorsi esclusi dall'autenticazione integrata.
$meta = Invoke-RestMethod "$apiUrl/api/meta"
Write-Host "      Catalogo: $($meta.content.topics) argomenti, $($meta.content.questions) domande, $($meta.content.problems) problemi"
if (-not $authMode) { $authMode = $meta.auth_mode }

if (-not $meta.ai_enabled) {
    Warn "AI non attiva su questa istanza (enable_ai = false)."
    Step "Fatto"
    Write-Host ""
    Write-Host "  App: $webUrl" -ForegroundColor Green
    Write-Host "  API: $apiUrl"
    Write-Host ""
    exit 0
}

Write-Host "      Modello : $($meta.ai_deployment) [$($meta.ai_family)]"

# Come ci si autentica al selftest dipende da come e' protetta l'istanza.
# Con Entra ID il codice condiviso non vale piu' nulla: l'autenticazione
# integrata di Container Apps risponde 401 a qualunque richiesta senza Bearer.
$headers = @{}
$motivo = ""
if ($authMode -eq "entra_id") {
    if (-not $entraClientId) {
        $motivo = "manca l'output entra_client_id: rilancia terraform apply."
    } else {
        # La Azure CLI e' gia' autenticata come te: se e' pre-autorizzata
        # sull'app registration (entra_allow_azure_cli = true) ottiene il token
        # in silenzio, senza schermata di consenso.
        $token = az account get-access-token --resource "api://$entraClientId" --query accessToken --output tsv 2>$null
        if ($LASTEXITCODE -eq 0 -and $token) {
            $headers["Authorization"] = "Bearer $($token.Trim())"
        } else {
            $motivo = "la Azure CLI non ha ottenuto un token per api://$entraClientId."
        }
    }
} elseif ($code) {
    $headers["X-Access-Code"] = $code
}

if ($motivo) {
    Warn "Selftest saltato: $motivo"
    Warn "  Il deploy e' comunque a posto: questo controllo richiede un token utente."
    Warn "  Per abilitarlo: metti entra_allow_azure_cli = true in terraform.tfvars,"
    Warn "  poi terraform -chdir=terraform apply."
    Warn "  In alternativa verifica dal browser: apri $webUrl, fai login e genera un piano."
} else {
    Write-Host "  Provo una generazione vera..."
    try {
        $test = Invoke-RestMethod "$apiUrl/api/ai/selftest" -Method Post -Headers $headers
        if ($test.ok) {
            Ok "AI funzionante ($($test.latency_ms) ms, api-version $($test.api_version_used))"
            if ($test.adapted) { Warn $test.hint }
        } else {
            Warn "L'AI risponde con un errore: $($test.error)"
            Warn "Suggerimento: $($test.hint)"
        }
    } catch {
        $errore = $_
        # Il messaggio cambia fra Windows PowerShell e PowerShell 7: lo stato
        # numerico e' l'unica cosa su cui si possa ragionare in entrambi.
        $stato = 0
        try { $stato = [int]$errore.Exception.Response.StatusCode } catch { }
        Warn "Selftest non riuscito: $errore"
        if ($stato -eq 401 -or "$errore" -match "\b401\b") {
            if ($authMode -eq "entra_id") {
                Warn "  401 con il login attivo: il token non e' stato accettato."
                Warn "  Controlla di aver fatto az login con l'account assegnato all'app."
            } else {
                Warn "  401: il codice di accesso non combacia con quello dell'istanza."
            }
        }
        Warn "  Verifica manuale: apri $webUrl e genera un piano."
    }
}

Step "Fatto"
Write-Host ""
Write-Host "  App: $webUrl" -ForegroundColor Green
Write-Host "  API: $apiUrl"
Write-Host ""
