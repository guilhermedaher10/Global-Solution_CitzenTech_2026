# Infraestrutura do MVP Ruas Escuras na Azure.
#
#   rg-ruasescuras (criado pelo bootstrap)
#   ├── Log Analytics            logs dos containers (cota diária: custo nunca dispara)
#   ├── Container Registry       imagens privadas; puxadas por identidade gerenciada, sem senha
#   ├── Identidade gerenciada    "crachá" do container para puxar a imagem (AcrPull)
#   ├── Container Apps Env       ambiente serverless (WorkloadProfiles/Consumption, via azapi), sem VM nem porta de admin
#   ├── Container App "visao"    API da Visão, HTTPS público, escala 0..N
#   └── Orçamento + alertas      e-mail em 50/80/100% do valor mensal
#
# Divisão de responsabilidade: o Terraform cria e mantém a INFRA. A VERSÃO da imagem em produção
# é trocada pelo pipeline (az containerapp update), por isso o Terraform ignora a imagem depois
# de criada (lifecycle.ignore_changes). Assim um "terraform apply" nunca volta a produção para
# uma versão antiga.

data "azurerm_resource_group" "app" {
  name = var.resource_group
}

data "azurerm_client_config" "atual" {}

resource "random_string" "sufixo" {
  length  = 6
  upper   = false
  special = false
  keepers = { rg = data.azurerm_resource_group.app.id }
}

locals {
  sufixo = random_string.sufixo.result
  local  = data.azurerm_resource_group.app.location
}

# ---------------------------------------------------------------- logs
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${var.prefixo}-${local.sufixo}"
  location            = local.local
  resource_group_name = data.azurerm_resource_group.app.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5 # teto de ingestão por dia: protege o crédito de estudante
  tags                = var.tags
}

# ---------------------------------------------------------------- registro de imagens
resource "azurerm_container_registry" "acr" {
  name                = "acr${var.prefixo}${local.sufixo}"
  location            = local.local
  resource_group_name = data.azurerm_resource_group.app.name
  sku                 = "Basic"
  admin_enabled       = false # sem usuário/senha: só identidades do Entra ID
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "visao" {
  name                = "id-${var.prefixo}-visao"
  location            = local.local
  resource_group_name = data.azurerm_resource_group.app.name
  tags                = var.tags
}

# Criado no 1º apply, feito pelo Owner da assinatura: o robô do pipeline NÃO pode conceder papéis
# (menor privilégio). Nos applies seguintes ele só lê esta atribuição.
resource "azurerm_role_assignment" "visao_puxa_imagem" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.visao.principal_id
  principal_type       = "ServicePrincipal"
}

# ---------------------------------------------------------------- Container Apps
# Ambiente criado pelo azapi (provedor oficial da Microsoft, fala direto com a API do Azure):
# sem "environmentMode", a Azure passou a criar ambientes no modo "Express" (preview), que
# ignora a configuração de registro privado e não puxa imagem do ACR com identidade gerenciada.
# O azurerm 4.x ainda não tem esse campo, então declaramos o modo tradicional explicitamente:
# WorkloadProfiles + perfil Consumption (serverless, paga só pelo uso, escala a zero).
resource "azapi_resource" "env" {
  type                      = "Microsoft.App/managedEnvironments@2026-07-01"
  name                      = "cae-${var.prefixo}-wp"
  parent_id                 = data.azurerm_resource_group.app.id
  location                  = local.local
  tags                      = var.tags
  schema_validation_enabled = false # versão da API mais nova que o schema embutido no provedor

  body = {
    properties = {
      environmentMode  = "WorkloadProfiles"
      workloadProfiles = [{ name = "Consumption", workloadProfileType = "Consumption" }]
      appLogsConfiguration = {
        destination = "log-analytics"
        logAnalyticsConfiguration = {
          customerId = azurerm_log_analytics_workspace.logs.workspace_id
        }
      }
    }
  }

  # a chave do workspace não aparece no plan nem nos logs do pipeline
  sensitive_body = {
    properties = {
      appLogsConfiguration = {
        logAnalyticsConfiguration = {
          sharedKey = azurerm_log_analytics_workspace.logs.primary_shared_key
        }
      }
    }
  }

  response_export_values = ["properties.environmentMode", "properties.defaultDomain"]
}

resource "azurerm_container_app" "visao" {
  name                         = "ca-${var.prefixo}-visao"
  container_app_environment_id = azapi_resource.env.id
  resource_group_name          = data.azurerm_resource_group.app.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.visao.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.visao.id
  }

  ingress {
    external_enabled = true # só HTTPS 443 público; não existe porta de administração
    target_port      = 8000
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.visao_min_replicas
    max_replicas = var.visao_max_replicas

    http_scale_rule {
      name                = "requisicoes-simultaneas"
      concurrent_requests = "10"
    }

    container {
      name   = "visao"
      image  = var.visao_imagem_inicial
      cpu    = var.visao_cpu
      memory = var.visao_memoria

      env {
        name  = "MAX_UPLOAD_MB"
        value = "10"
      }
      env {
        name  = "MODELO_NOME"
        value = "yolo26-postes"
      }

      startup_probe {
        transport               = "HTTP"
        path                    = "/saude"
        port                    = 8000
        initial_delay           = 5
        interval_seconds        = 5
        failure_count_threshold = 24 # até 2 min para carregar o PyTorch + modelo
      }
      liveness_probe {
        transport = "HTTP"
        path      = "/saude"
        port      = 8000
      }
    }
  }

  lifecycle {
    # a versão em produção é do pipeline (az containerapp update), não do Terraform
    ignore_changes = [template[0].container[0].image, template[0].container[0].env]
  }

  depends_on = [azurerm_role_assignment.visao_puxa_imagem]
}

# ---------------------------------------------------------------- custo
resource "azurerm_consumption_budget_resource_group" "orcamento" {
  name              = "orcamento-${var.prefixo}"
  resource_group_id = data.azurerm_resource_group.app.id
  amount            = var.orcamento_mensal
  time_grain        = "Monthly"

  time_period {
    start_date = var.inicio_orcamento
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = var.emails_alerta
    }
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Forecasted" # avisa ANTES: previsão do mês passa do orçamento
    contact_emails = var.emails_alerta
  }
}
