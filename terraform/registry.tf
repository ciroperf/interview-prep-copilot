# Registro immagini opzionale. Di default non viene creato: un package pubblico
# su GHCR costa zero e Container Apps lo tira senza credenziali.

resource "azurerm_container_registry" "this" {
  count               = var.create_container_registry ? 1 : 0
  name                = substr("cr${local.compact_name}${random_string.suffix.result}", 0, 50)
  resource_group_name = local.resource_group.name
  location            = local.resource_group.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.common_tags
}

resource "azurerm_role_assignment" "acr_pull" {
  count                = var.create_container_registry ? 1 : 0
  scope                = azurerm_container_registry.this[0].id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

locals {
  registry_server = var.create_container_registry ? azurerm_container_registry.this[0].login_server : var.registry_server
  # Il registro va dichiarato nella Container App solo se serve autenticarsi:
  # per un package pubblico si lascia fuori e il pull avviene anonimo.
  needs_registry_block = var.create_container_registry || var.registry_username != ""
}
