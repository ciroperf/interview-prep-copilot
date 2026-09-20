#!/usr/bin/env bash
# Crea le risorse per lo stato remoto di Terraform.
# Va eseguito una volta sola, prima del primo `terraform init` con backend azurerm.
set -euo pipefail

LOCATION="${LOCATION:-swedencentral}"
RG="${RG:-rg-tfstate}"
CONTAINER="${CONTAINER:-tfstate}"
SUFFIX="$(tr -dc 'a-z0-9' </dev/urandom | head -c 5)"
ACCOUNT="${ACCOUNT:-sttfstate${SUFFIX}}"

echo "Resource group : $RG ($LOCATION)"
echo "Storage account: $ACCOUNT"
echo

az group create --name "$RG" --location "$LOCATION" --output none

az storage account create \
  --name "$ACCOUNT" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --output none

# Il versioning permette di recuperare uno stato sovrascritto per errore.
az storage account blob-service-properties update \
  --account-name "$ACCOUNT" \
  --resource-group "$RG" \
  --enable-versioning true \
  --output none

USER_ID="$(az ad signed-in-user show --query id -o tsv)"
ACCOUNT_ID="$(az storage account show --name "$ACCOUNT" --resource-group "$RG" --query id -o tsv)"

az role assignment create \
  --assignee "$USER_ID" \
  --role "Storage Blob Data Contributor" \
  --scope "$ACCOUNT_ID" \
  --output none

# La propagazione dell'RBAC richiede qualche secondo prima che il container si crei.
sleep 20

az storage container create \
  --name "$CONTAINER" \
  --account-name "$ACCOUNT" \
  --auth-mode login \
  --output none

cat <<MSG

Fatto. Metti questo in terraform/backend.tf:

terraform {
  backend "azurerm" {
    resource_group_name  = "$RG"
    storage_account_name = "$ACCOUNT"
    container_name       = "$CONTAINER"
    key                  = "interview-prep-copilot.tfstate"
    use_azuread_auth     = true
  }
}

Poi: terraform init -migrate-state
MSG
