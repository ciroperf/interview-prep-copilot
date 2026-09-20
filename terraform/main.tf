# Risorse comuni: resource group, naming e identità dell'applicazione.

locals {
  base_name = "${var.name_prefix}-${var.environment}"

  common_tags = merge(
    {
      project     = "interview-prep-copilot"
      environment = var.environment
      managed_by  = "terraform"
    },
    var.tags,
  )

  resource_group_name = var.resource_group_name != "" ? var.resource_group_name : "rg-${local.base_name}"

  # Storage account e registro non ammettono trattini e devono essere univoci
  # a livello globale: da qui il suffisso casuale.
  compact_name = replace(local.base_name, "-", "")
}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

resource "random_password" "access_code" {
  length  = 20
  special = false
}

locals {
  access_code = var.access_code != "" ? var.access_code : random_password.access_code.result
}

resource "azurerm_resource_group" "this" {
  count    = var.create_resource_group ? 1 : 0
  name     = local.resource_group_name
  location = var.location
  tags     = local.common_tags
}

data "azurerm_resource_group" "existing" {
  count = var.create_resource_group ? 0 : 1
  name  = local.resource_group_name
}

locals {
  resource_group = var.create_resource_group ? azurerm_resource_group.this[0] : data.azurerm_resource_group.existing[0]
}

# Identità dell'applicazione. È user-assigned e non system-assigned perché così
# le assegnazioni RBAC si possono creare nello stesso apply che crea la Container
# App, senza il ciclo "prima l'app, poi il ruolo, poi di nuovo l'app".
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${local.base_name}"
  resource_group_name = local.resource_group.name
  location            = local.resource_group.location
  tags                = local.common_tags
}
