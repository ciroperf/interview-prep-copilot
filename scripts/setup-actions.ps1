<#
.SYNOPSIS
    Configura il deploy automatico da GitHub Actions. Da lanciare una volta sola.

.DESCRIPTION
    Fa tutto quello che docs/deploy.md descrive a mano:

      1. crea (o riusa) l'app registration usata per il login federato;
      2. le assegna il ruolo Contributor sul SOLO resource group del progetto;
      3. crea la credenziale federata per l'ambiente "production" del repo;
      4. legge gli output di Terraform;
      5. scrive i segreti nell'ambiente "production" con la CLI di GitHub.

    E' idempotente: rilanciarlo non duplica niente e aggiorna i segreti ai
    valori correnti. Nessun valore segreto viene stampato a schermo.

    Dopo questo, un push su main che tocca backend/ rilascia l'API e uno che
    tocca frontend/ ripubblica il sito, senza piu' passare da deploy.ps1.

.PARAMETER AppName
    Nome dell'app registration. Default "interview-prep-copilot-deploy".

.PARAMETER Environment
    Ambiente GitHub a cui legare credenziale e segreti. Default "production",
    che e' quello dichiarato dai workflow.

.EXAMPLE
    az login
    gh auth login
    .\scripts\setup-actions.ps1
#>
[CmdletBinding()]
param(
    [string]$AppName = "interview-prep-copilot-deploy",
    [string]$Environment = "production"
)

$ErrorActionPreference = "Stop"
# I comandi nativi segnalano gli errori con l'exit code, non con le eccezioni:
# li controlliamo noi, altrimenti PowerShell 7 tratta stderr come errore fatale.
$PSNativeCommandUseErrorActionPreference = $false

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "  OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  !   $text" -ForegroundColor Yellow }
function Fail($text) { Write-Host "  X   $text" -ForegroundColor Red; exit 1 }

$root = Split-Path -Parent $PSScriptRoot
$tf   = Join-Path $root "terraform"

# --- prerequisiti ----------------------------------------------------------

Step "Prerequisiti"

foreach ($tool in @(
    @{ Nome = "az";        Aiuto = "https://aka.ms/installazurecli" },
    @{ Nome = "gh";        Aiuto = "https://cli.github.com" },
    @{ Nome = "terraform"; Aiuto = "https://developer.hashicorp.com/terraform/install" }
)) {
    if (-not (Get-Command $tool.Nome -ErrorAction SilentlyContinue)) {
        Fail "$($tool.Nome) non trovato. Installalo: $($tool.Aiuto)"
    }
}
Ok "az, gh e terraform disponibili"

$account = az account show 2>$null | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { Fail "Non sei autenticato su Azure. Lancia: az login" }
Ok "Azure: $($account.name)"

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Non sei autenticato su GitHub. Lancia: gh auth login" }

# Il repository si deduce dal remote, cosi' il subject della credenziale
# federata non puo' divergere da dove girano davvero i workflow.
$repo = gh repo view --json nameWithOwner -q .nameWithOwner 2>$null
if ($LASTEXITCODE -ne 0 -or -not $repo) { Fail "Non riesco a dedurre il repository da questa cartella" }
Ok "GitHub: $repo"

# --- output di Terraform ---------------------------------------------------

Step "Lettura degli output di Terraform"

function Get-TfOutput([string]$Name, [switch]$Optional) {
    $value = terraform output -raw $Name 2>$null
    if ($LASTEXITCODE -ne 0) {
        if ($Optional) { return "" }
        Fail "Output '$Name' non disponibile. Hai gia' lanciato scripts/deploy.ps1?"
    }
    return "$value".Trim()
}

Push-Location $tf
try {
    $rg         = Get-TfOutput resource_group_name
    $appName    = Get-TfOutput api_container_app_name
    $apiUrl     = Get-TfOutput api_url
    $swaToken   = Get-TfOutput static_web_app_deployment_token
    $authMode   = Get-TfOutput auth_mode        -Optional
    $entraId    = Get-TfOutput entra_client_id  -Optional
    $entraTen   = Get-TfOutput entra_tenant_id  -Optional
    $entraScope = Get-TfOutput entra_api_scope  -Optional
} finally { Pop-Location }

Ok "Resource group: $rg"
Ok "Container App: $appName"

# --- app registration e federazione ---------------------------------------

Step "App registration per il login federato"

$appId = az ad app list --display-name $AppName --query "[0].appId" -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $appId) {
    $appId = az ad app create --display-name $AppName --query appId -o tsv
    if ($LASTEXITCODE -ne 0) { Fail "Creazione dell'app registration fallita. Serve il permesso di crearne nel tenant." }
    Ok "App registration creata"
} else {
    Ok "App registration gia' esistente, la riuso"
}

az ad sp show --id $appId 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    az ad sp create --id $appId --output none
    if ($LASTEXITCODE -ne 0) { Fail "Creazione del service principal fallita" }
    Ok "Service principal creato"
} else {
    Ok "Service principal gia' presente"
}

# Il ruolo e' limitato al resource group del progetto: non serve di piu' e
# un principale con accesso all'intera sottoscrizione e' un rischio inutile.
$scope = "/subscriptions/$($account.id)/resourceGroups/$rg"
$esistente = az role assignment list --assignee $appId --scope $scope --role Contributor --query "[0].id" -o tsv 2>$null
if (-not $esistente) {
    az role assignment create --assignee $appId --role Contributor --scope $scope --output none
    if ($LASTEXITCODE -ne 0) { Fail "Assegnazione del ruolo fallita" }
    Ok "Ruolo Contributor assegnato sul solo resource group"
} else {
    Ok "Ruolo gia' assegnato"
}

$objId = az ad app show --id $appId --query id -o tsv

# GitHub ha due formati di subject e un repository ne usa uno solo, ma quale
# dipende da quando e' stato creato: dal 15 luglio 2026 i nuovi repository -
# e quelli rinominati o trasferiti dopo quella data - presentano il formato
# "immutabile", che accanto ai nomi porta gli ID numerici di proprietario e
# repository. I nomi si possono riciclare, gli ID no, ed e' il motivo del
# cambio. Creiamo entrambe le credenziali: costano nulla, e cosi' lo script
# funziona senza sapere in che regime sta il repository - e continua a
# funzionare se il repository ci passa domani.
$ids = gh api "repos/$repo" --jq '{owner: .owner.id, repo: .id}' 2>$null | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or -not $ids) { Fail "Non riesco a leggere gli ID numerici del repository" }

$ownerName, $repoName = $repo -split "/", 2
$soggetti = [ordered]@{
    "github-$Environment"           = "repo:${repo}:environment:$Environment"
    "github-$Environment-immutable" = "repo:$ownerName@$($ids.owner)/$repoName@$($ids.repo):environment:$Environment"
}

foreach ($nome in $soggetti.Keys) {
    $subject = $soggetti[$nome]
    $credEsiste = az ad app federated-credential list --id $objId --query "[?subject=='$subject'] | [0].id" -o tsv 2>$null
    if ($credEsiste) {
        Ok "Credenziale '$nome' gia' presente"
        continue
    }

    $parametri = @{
        name      = $nome
        issuer    = "https://token.actions.githubusercontent.com"
        subject   = $subject
        audiences = @("api://AzureADTokenExchange")
    } | ConvertTo-Json -Compress

    # Il JSON passa da un file: le virgolette sulla riga di comando si
    # comportano in modo diverso fra le shell e qui si rompono facilmente.
    $tmp = New-TemporaryFile
    try {
        Set-Content -Path $tmp -Value $parametri -Encoding utf8
        az ad app federated-credential create --id $objId --parameters "@$tmp" --output none
        if ($LASTEXITCODE -ne 0) { Fail "Creazione della credenziale '$nome' fallita" }
    } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
    Ok "Credenziale '$nome' creata per $subject"
}

# --- segreti ---------------------------------------------------------------

Step "Segreti nell'ambiente '$Environment'"

$segreti = [ordered]@{
    AZURE_CLIENT_ID                  = $appId
    AZURE_TENANT_ID                  = $account.tenantId
    AZURE_SUBSCRIPTION_ID            = $account.id
    AZURE_RESOURCE_GROUP             = $rg
    AZURE_CONTAINER_APP_NAME         = $appName
    AZURE_STATIC_WEB_APPS_API_TOKEN  = $swaToken
    API_BASE_URL                     = $apiUrl
}

if ($authMode -eq "entra_id") {
    $segreti["ENTRA_CLIENT_ID"] = $entraId
    $segreti["ENTRA_TENANT_ID"] = $entraTen
    $segreti["ENTRA_API_SCOPE"] = $entraScope
    Ok "Login Microsoft attivo: aggiungo anche i tre segreti ENTRA_*"
} else {
    Warn "auth_mode = '$authMode': salto i segreti ENTRA_* (si entra con il codice)"
}

foreach ($nome in $segreti.Keys) {
    $valore = $segreti[$nome]
    if ([string]::IsNullOrWhiteSpace($valore)) {
        Warn "$nome : valore vuoto, lo salto"
        continue
    }
    # Senza --body, gh legge il valore dallo standard input: cosi' non finisce
    # ne' nella riga di comando ne' nella cronologia della shell.
    $valore | gh secret set $nome --env $Environment --repo $repo 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "Impossibile scrivere il segreto $nome" }
    Ok "$nome = ***"
}

Step "Fatto"
Write-Host @"
  Il deploy automatico e' attivo.

    push su main che tocca backend/   ->  ricostruisce e rilascia l'API
    push su main che tocca frontend/  ->  ripubblica il sito

  Per pubblicare subito quello che c'e' gia' su main, senza aspettare un push:

    gh workflow run deploy-backend.yml
    gh workflow run deploy-frontend.yml
    gh run watch

  L'ambiente '$Environment' potrebbe avere una regola di approvazione: se il
  job resta in attesa, approvalo dalla pagina Actions del repository.
"@ -ForegroundColor Gray
