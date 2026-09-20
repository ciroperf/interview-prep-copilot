# Login Microsoft (Entra ID) al posto del codice di accesso condiviso.
#
# Il flusso e' OAuth2 Authorization Code con PKCE: il frontend ottiene un token
# con MSAL, lo manda come Bearer, e l'autenticazione integrata di Container Apps
# lo valida prima che la richiesta arrivi all'applicazione. Il backend non
# verifica firme: riceve l'identita' gia' validata negli header X-MS-CLIENT-*.
#
# Si attiva con enable_entra_auth = true. Spento, resta il codice condiviso.

locals {
  entra_enabled = var.enable_entra_auth

  frontend_url = "https://${azurerm_static_web_app.this.default_host_name}"

  # Gli URI di reindirizzamento ammessi dopo il login. Localhost serve per
  # sviluppare contro l'API vera senza dover ripubblicare il frontend.
  raw_redirect_uris = concat(
    [local.frontend_url],
    var.entra_extra_redirect_uris,
    var.entra_allow_localhost ? ["http://localhost:5173"] : [],
  )

  # Entra ID rifiuta un redirect URI privo di path che non finisca con "/":
  # "https://esempio.it" non e' valido, "https://esempio.it/" si'. Normalizziamo
  # qui invece di pretenderlo da chi compila le variabili. MSAL e' configurato
  # per usare la stessa forma (vedi frontend/src/lib/auth.ts): il confronto che
  # fa Entra e' esatto, quindi le due devono coincidere.
  redirect_uris = [
    for uri in local.raw_redirect_uris :
    can(regex("^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]+$", uri)) ? "${uri}/" : uri
  ]
}

data "azuread_client_config" "current" {
  count = local.entra_enabled ? 1 : 0
}

resource "random_uuid" "scope" {
  count = local.entra_enabled ? 1 : 0
}

resource "azuread_application" "app" {
  count            = local.entra_enabled ? 1 : 0
  display_name     = "Interview Prep Copilot (${var.environment})"
  owners           = [data.azuread_client_config.current[0].object_id]
  sign_in_audience = "AzureADMyOrg"

  # Una sola app registration fa da client SPA e da API: per un'applicazione
  # con un solo frontend, due registrazioni sarebbero cerimonia inutile.
  single_page_application {
    redirect_uris = local.redirect_uris
  }

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = random_uuid.scope[0].result
      value                      = "access_as_user"
      type                       = "User"
      enabled                    = true
      admin_consent_display_name = "Accedi a Interview Prep Copilot"
      admin_consent_description  = "Consente all'app di chiamare l'API per conto dell'utente."
      user_consent_display_name  = "Accedi a Interview Prep Copilot"
      user_consent_description   = "Consente all'app di chiamare l'API per tuo conto."
    }
  }

  # L'app che chiede il token e quella che lo riceve sono la stessa: senza
  # questa pre-autorizzazione l'utente vedrebbe una schermata di consenso
  # superflua al primo accesso.
  lifecycle {
    ignore_changes = [identifier_uris]
  }
}

# L'identifier URI contiene il client id, che esiste solo dopo la creazione:
# per questo sta in una risorsa a parte e non dentro azuread_application.
resource "azuread_application_identifier_uri" "app" {
  count          = local.entra_enabled ? 1 : 0
  application_id = azuread_application.app[0].id
  identifier_uri = "api://${azuread_application.app[0].client_id}"
}

resource "azuread_application_pre_authorized" "spa" {
  count                = local.entra_enabled ? 1 : 0
  application_id       = azuread_application.app[0].id
  authorized_client_id = azuread_application.app[0].client_id
  permission_ids       = [random_uuid.scope[0].result]

  depends_on = [azuread_application_identifier_uri.app]
}

resource "azuread_service_principal" "app" {
  count     = local.entra_enabled ? 1 : 0
  client_id = azuread_application.app[0].client_id
  owners    = [data.azuread_client_config.current[0].object_id]

  # true significa: entra solo chi e' stato assegnato esplicitamente.
  # false: chiunque abbia un account nel tenant.
  app_role_assignment_required = var.entra_restrict_to_owner
}

# Con assignment_required, solo gli utenti assegnati esplicitamente entrano:
# è la differenza fra "chiunque nel tenant" e "io".
resource "azuread_app_role_assignment" "owner" {
  count               = local.entra_enabled && var.entra_restrict_to_owner ? 1 : 0
  app_role_id         = "00000000-0000-0000-0000-000000000000" # nessun ruolo: solo accesso
  principal_object_id = data.azuread_client_config.current[0].object_id
  resource_object_id  = azuread_service_principal.app[0].object_id
}

# L'autenticazione integrata di Container Apps non ha una risorsa dedicata nel
# provider azurerm: si configura con un template ARM sul sotto-oggetto
# authConfigs. Evita di aggiungere il provider azapi solo per questo.
resource "azurerm_resource_group_template_deployment" "auth" {
  count               = local.entra_enabled ? 1 : 0
  name                = "authconfig-${local.base_name}"
  resource_group_name = local.resource_group.name
  deployment_mode     = "Incremental"

  parameters_content = jsonencode({
    containerAppName = { value = azurerm_container_app.api.name }
    clientId         = { value = azuread_application.app[0].client_id }
    tenantId         = { value = data.azuread_client_config.current[0].tenant_id }
    allowedAudiences = {
      value = [
        "api://${azuread_application.app[0].client_id}",
        azuread_application.app[0].client_id,
      ]
    }
  })

  template_content = jsonencode({
    "$schema"      = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    contentVersion = "1.0.0.0"
    parameters = {
      containerAppName = { type = "string" }
      clientId         = { type = "string" }
      tenantId         = { type = "string" }
      allowedAudiences = { type = "array" }
    }
    resources = [
      {
        type       = "Microsoft.App/containerApps/authConfigs"
        apiVersion = "2024-03-01"
        name       = "[concat(parameters('containerAppName'), '/current')]"
        properties = {
          platform = {
            enabled = true
          }
          globalValidation = {
            # Il frontend è una SPA che chiama l'API da un'altra origine: un
            # redirect al login non avrebbe senso su una chiamata XHR, quindi
            # si risponde 401 e sarà MSAL a gestire il login.
            unauthenticatedClientAction = "Return401"
            # Due percorsi restano pubblici: l'health check, altrimenti le probe
            # di Container Apps prenderebbero 401 e la revisione non partirebbe
            # mai, e /api/meta, che il frontend interroga prima del login per
            # sapere come autenticarsi. Nessuno dei due espone dati riservati.
            excludedPaths = ["/api/health", "/api/meta"]
          }
          identityProviders = {
            azureActiveDirectory = {
              enabled = true
              registration = {
                clientId = "[parameters('clientId')]"
                # Nessun client secret: qui si valida soltanto il token che la
                # SPA ha gia' ottenuto, non si esegue un flusso server-side.
                openIdIssuer = "[concat('https://login.microsoftonline.com/', parameters('tenantId'), '/v2.0')]"
              }
              validation = {
                allowedAudiences = "[parameters('allowedAudiences')]"
              }
            }
          }
        }
      }
    ]
  })
}
