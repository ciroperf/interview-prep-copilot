# Azure AI Foundry: account AI Services più un deployment del modello.
# Il costo è a consumo sui token: senza traffico non si paga nulla.

# kind = "AIServices" è l'account multi-servizio di AI Foundry: espone gli
# endpoint Azure OpenAI e permette di aggiungere altri modelli in seguito.
resource "azurerm_cognitive_account" "ai" {
  count               = var.enable_ai ? 1 : 0
  name                = "ai-${local.base_name}-${random_string.suffix.result}"
  resource_group_name = local.resource_group.name
  location            = var.ai_location
  kind                = "AIServices"
  sku_name            = "S0"

  # Il sottodominio dedicato è obbligatorio per autenticarsi con Entra ID.
  custom_subdomain_name = "ai-${local.compact_name}-${random_string.suffix.result}"
  # Con la managed identity la chiave non serve: disabilitarla toglie di mezzo
  # un segreto da custodire e ruotare.
  local_auth_enabled = !var.ai_use_managed_identity

  tags = local.common_tags
}

resource "azurerm_cognitive_deployment" "chat" {
  count                = var.enable_ai ? 1 : 0
  name                 = var.ai_model_name
  cognitive_account_id = azurerm_cognitive_account.ai[0].id

  model {
    format  = "OpenAI"
    name    = var.ai_model_name
    version = var.ai_model_version
  }

  sku {
    name     = var.ai_deployment_sku
    capacity = var.ai_capacity
  }
}

# "Cognitive Services OpenAI User" basta per inferenza: non concede la gestione
# dei deployment, quindi l'app non può modificare la configurazione del modello.
resource "azurerm_role_assignment" "ai_user" {
  count                = var.enable_ai && var.ai_use_managed_identity ? 1 : 0
  scope                = azurerm_cognitive_account.ai[0].id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}
