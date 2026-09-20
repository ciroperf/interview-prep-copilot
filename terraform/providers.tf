provider "azurerm" {
  features {
    resource_group {
      # Evita che un apply distrugga risorse create a mano nello stesso gruppo.
      prevent_deletion_if_contains_resources = true
    }
    cognitive_account {
      # Senza questo l'account AI resta in soft-delete e il nome non è riusabile.
      purge_soft_delete_on_destroy = true
    }
  }
  # La sottoscrizione si passa con ARM_SUBSCRIPTION_ID o con -var subscription_id.
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}
