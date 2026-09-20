# Log Analytics serve a Container Apps. La quota giornaliera è la protezione
# contro il costo che può esplodere davvero: un loop di errori che scrive log.

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.base_name}"
  resource_group_name = local.resource_group.name
  location            = local.resource_group.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  daily_quota_gb      = var.log_daily_quota_gb
  tags                = local.common_tags
}

# Avviso di spesa: non blocca nulla, ma evita di accorgersi del problema a fine mese.
resource "azurerm_consumption_budget_resource_group" "this" {
  count             = var.monthly_budget_eur > 0 && var.budget_alert_email != "" ? 1 : 0
  name              = "budget-${local.base_name}"
  resource_group_id = local.resource_group.id

  amount     = var.monthly_budget_eur
  time_grain = "Monthly"

  time_period {
    # Azure vuole il primo giorno di un mese: usiamo quello corrente, così il
    # budget traccia la spesa da subito invece che dal mese prossimo.
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  # Avviso all'80% del previsto e alla proiezione del 100%: il secondo arriva
  # prima, quando il ritmo di spesa lascia prevedere lo sforamento.
  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.budget_alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = [var.budget_alert_email]
  }

  lifecycle {
    # start_date deriva da timestamp(): senza questo ogni plan risulterebbe modificato.
    ignore_changes = [time_period]
  }
}
