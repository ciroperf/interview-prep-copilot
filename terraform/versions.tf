terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      # 4.44 e' la prima versione verificata che conosce il blocco cors
      # dell'ingress di Container Apps: con una precedente l'apply si ferma su
      # "Blocks of type cors are not expected here".
      source  = "hashicorp/azurerm"
      version = "~> 4.44"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
