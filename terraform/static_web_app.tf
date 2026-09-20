# Il frontend è statico: la Static Web App in piano Free lo serve su CDN globale
# con HTTPS e dominio personalizzato inclusi, a costo zero.

resource "azurerm_static_web_app" "this" {
  name                = "swa-${local.base_name}"
  resource_group_name = local.resource_group.name
  # Il piano Free è disponibile solo in alcune regioni: westeurope è la più
  # vicina all'Italia fra quelle supportate.
  location                     = "westeurope"
  sku_tier                     = "Free"
  sku_size                     = "Free"
  preview_environments_enabled = false
  tags                         = local.common_tags
}
