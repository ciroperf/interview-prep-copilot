output "resource_group_name" {
  description = "Resource group che contiene tutto."
  value       = local.resource_group.name
}

output "api_url" {
  description = "URL pubblico dell'API. Va messo in VITE_API_BASE_URL per il frontend."
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "api_container_app_name" {
  description = "Nome della Container App, serve ad `az containerapp update` nel deploy."
  value       = azurerm_container_app.api.name
}

output "frontend_url" {
  description = "URL del frontend sulla Static Web App."
  value       = "https://${azurerm_static_web_app.this.default_host_name}"
}

output "static_web_app_name" {
  description = "Nome della Static Web App."
  value       = azurerm_static_web_app.this.name
}

output "static_web_app_deployment_token" {
  description = "Token di deploy della SWA. Va nel secret AZURE_STATIC_WEB_APPS_API_TOKEN."
  value       = azurerm_static_web_app.this.api_key
  sensitive   = true
}

output "access_code" {
  description = "Codice di accesso all'app. Leggilo con: terraform output -raw access_code"
  value       = local.access_code
  sensitive   = true
}

output "storage_account_name" {
  description = "Storage account con tabelle e blob."
  value       = azurerm_storage_account.this.name
}

output "managed_identity_client_id" {
  description = "Client ID dell'identità usata dall'app."
  value       = azurerm_user_assigned_identity.app.client_id
}

output "container_registry_login_server" {
  description = "Registro da cui viene tirata l'immagine."
  value       = local.registry_server
}

output "ai_endpoint" {
  description = "Endpoint di Azure AI Foundry. Vuoto se enable_ai = false."
  value       = local.ai_endpoint
}

output "ai_deployment_name" {
  description = "Nome del deployment del modello."
  value       = var.enable_ai ? azurerm_cognitive_deployment.chat[0].name : ""
}

output "next_steps" {
  description = "Cosa fare subito dopo il primo apply."
  value       = <<-EOT
    1. Pubblica l'immagine dell'API e aggiorna la Container App:
         az containerapp update -n ${azurerm_container_app.api.name} \
           -g ${local.resource_group.name} --image <registro>/interview-prep-copilot-api:<tag>

    2. Pubblica il frontend, avendo compilato con:
         VITE_API_BASE_URL=https://${azurerm_container_app.api.ingress[0].fqdn}

    3. Prendi il codice di accesso:
         terraform output -raw access_code

    4. Apri: https://${azurerm_static_web_app.this.default_host_name}
  EOT
}


# ---------------------------------------------------------------------------
# Autenticazione (valorizzati solo con enable_entra_auth = true)
# ---------------------------------------------------------------------------

output "entra_client_id" {
  description = "Client ID dell'app registration. Va in VITE_ENTRA_CLIENT_ID."
  value       = local.entra_enabled ? azuread_application.app[0].client_id : ""
}

output "entra_tenant_id" {
  description = "Tenant ID. Va in VITE_ENTRA_TENANT_ID."
  value       = local.entra_enabled ? data.azuread_client_config.current[0].tenant_id : ""
}

output "entra_api_scope" {
  description = "Scope da richiedere con MSAL. Va in VITE_ENTRA_API_SCOPE."
  value = local.entra_enabled ? (
    "api://${azuread_application.app[0].client_id}/access_as_user"
  ) : ""
}

output "auth_mode" {
  description = "Come si accede all'app su questa istanza."
  value       = local.entra_enabled ? "entra_id" : "access_code"
}
