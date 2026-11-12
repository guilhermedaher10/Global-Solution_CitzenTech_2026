terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # State FORA do repositório: Storage Account criado por scripts/bootstrap-azure.ps1.
  # Acesso só por login Entra ID (a conta não aceita chave compartilhada).
  # Os nomes vêm por -backend-config (ver README), para nada da assinatura ficar no código.
  backend "azurerm" {
    container_name   = "tfstate"
    key              = "ruas-escuras.tfstate"
    use_azuread_auth = true
  }
}

provider "azurerm" {
  features {}
  # ARM_SUBSCRIPTION_ID / ARM_TENANT_ID / ARM_CLIENT_ID (+ ARM_USE_OIDC no pipeline) vêm do ambiente.
  # O robô do pipeline não tem permissão na assinatura toda: os provedores já foram registrados
  # pelo bootstrap, então o Terraform não tenta registrá-los.
  resource_provider_registrations = "none"
  storage_use_azuread             = true
}
