# Persistenza: Table Storage per i documenti, Blob per i CV (se abilitato).
# È il backend più economico disponibile su Azure: per un'app mono-utente
# la spesa è dell'ordine di pochi centesimi l'anno.

resource "azurerm_storage_account" "this" {
  name                = substr("st${local.compact_name}${random_string.suffix.result}", 0, 24)
  resource_group_name = local.resource_group.name
  location            = local.resource_group.location

  account_tier             = "Standard"
  account_replication_type = "LRS" # Dati ricostruibili: la ridondanza geografica non serve
  account_kind             = "StorageV2"
  access_tier              = "Hot"

  https_traffic_only_enabled      = true
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  # L'app non usa mai le chiavi dell'account: si autentica con la managed identity
  # e i ruoli RBAC assegnati più sotto. Restano abilitate perché il provider
  # Terraform le usa per creare il container blob; per disattivarle serve dare a
  # chi lancia l'apply il ruolo "Storage Blob Data Contributor" e impostare
  # storage_use_azuread nel provider. Vedi docs/security.md.
  shared_access_key_enabled = var.storage_shared_access_key_enabled

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }

  tags = local.common_tags
}

resource "azurerm_storage_container" "cv" {
  name                  = "cv-uploads"
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

# La managed identity dell'app deve poter leggere e scrivere tabelle e blob.
resource "azurerm_role_assignment" "table_data" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "blob_data" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}
