# L'API gira su Container Apps in profilo Consumption. Con min_replicas = 0
# l'app si spegne quando non la usi e il piano gratuito mensile (180.000 vCPU-s
# e 360.000 GiB-s) copre abbondantemente un uso personale.

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-${local.base_name}"
  resource_group_name        = local.resource_group.name
  location                   = local.resource_group.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  tags                       = local.common_tags
}

locals {
  # La Static Web App deve poter chiamare l'API: il suo hostname entra nella CORS.
  cors_origins = join(",", concat(
    ["https://${azurerm_static_web_app.this.default_host_name}"],
    var.allowed_origins,
  ))

  ai_endpoint = var.enable_ai ? azurerm_cognitive_account.ai[0].endpoint : ""

  app_env = merge(
    {
      ENVIRONMENT                = var.environment
      CORS_ORIGINS               = local.cors_origins
      STORAGE_BACKEND            = "azure_tables"
      AZURE_STORAGE_ACCOUNT_NAME = azurerm_storage_account.this.name
      AZURE_BLOB_CONTAINER       = azurerm_storage_container.cv.name
      STORE_CV_FILES             = tostring(var.store_cv_files)
      ENABLE_CODE_EXECUTION      = tostring(var.enable_code_execution)
      AZURE_OPENAI_ENDPOINT      = local.ai_endpoint
      AZURE_OPENAI_DEPLOYMENT    = var.enable_ai ? azurerm_cognitive_deployment.chat[0].name : ""
      AZURE_OPENAI_API_VERSION   = var.ai_api_version
      AI_MODEL_FAMILY            = var.ai_model_family
      AI_REASONING_EFFORT        = var.ai_reasoning_effort
      # DefaultAzureCredential va indirizzata all'identità giusta: senza questo,
      # in un container con più identità disponibili sceglierebbe a caso.
      AZURE_CLIENT_ID = azurerm_user_assigned_identity.app.client_id
    },
  )
}

resource "azurerm_container_app" "api" {
  name                         = "ca-${local.base_name}-api"
  resource_group_name          = local.resource_group.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = local.common_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  dynamic "registry" {
    for_each = local.needs_registry_block ? [1] : []
    content {
      server = local.registry_server
      # Con ACR ci si autentica con la managed identity, senza segreti.
      identity             = var.create_container_registry ? azurerm_user_assigned_identity.app.id : null
      username             = var.create_container_registry ? null : var.registry_username
      password_secret_name = var.create_container_registry ? null : "registry-password"
    }
  }

  dynamic "secret" {
    for_each = (!var.create_container_registry && var.registry_username != "") ? [1] : []
    content {
      name  = "registry-password"
      value = var.registry_password
    }
  }

  secret {
    name  = "access-code"
    value = local.access_code
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "api"
      image  = var.container_image
      cpu    = var.cpu
      memory = var.memory

      dynamic "env" {
        for_each = local.app_env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name        = "ACCESS_CODE"
        secret_name = "access-code"
      }

      liveness_probe {
        transport        = "HTTP"
        path             = "/api/health"
        port             = 8000
        initial_delay    = 5
        interval_seconds = 30
      }

      readiness_probe {
        transport        = "HTTP"
        path             = "/api/health"
        port             = 8000
        interval_seconds = 10
      }
    }

    # Con scale-to-zero la prima richiesta paga il cold start. Una sola regola
    # HTTP basta: il traffico di un utente singolo non giustifica altro.
    http_scale_rule {
      name                = "http"
      concurrent_requests = 20
    }
  }

  lifecycle {
    # L'immagine la aggiorna la pipeline di deploy a ogni rilascio: se Terraform
    # la gestisse, ogni apply riporterebbe l'app alla versione del default.
    ignore_changes = [template[0].container[0].image]
  }

  # I ruoli devono esistere prima che il container parta: al primo avvio l'app
  # apre subito le tabelle e ricarica gli argomenti aggiunti agli annunci.
  depends_on = [
    azurerm_role_assignment.table_data,
    azurerm_role_assignment.blob_data,
    azurerm_role_assignment.ai_user,
  ]
}
