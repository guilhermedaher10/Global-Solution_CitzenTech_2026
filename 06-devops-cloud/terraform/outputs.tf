output "url_visao" {
  description = "URL pública (HTTPS) da API da Visão"
  value       = "https://${azurerm_container_app.visao.ingress[0].fqdn}"
}

output "modo_ambiente" {
  description = "Deve ser WorkloadProfiles (não Express)"
  value       = azapi_resource.env.output.properties.environmentMode
}

output "acr_login_server" {
  description = "Registro onde o pipeline publica as imagens"
  value       = azurerm_container_registry.acr.login_server
}

output "acr_nome" {
  value = azurerm_container_registry.acr.name
}

output "container_app_nome" {
  value = azurerm_container_app.visao.name
}

output "central_tabela_url" {
  description = "Tabela da central de chamados (variável CENTRAL_TABELA_URL do container)"
  value       = "${azurerm_storage_account.central.primary_table_endpoint}${azapi_resource.tabela_chamados.name}"
}

output "identidade_client_id" {
  description = "Client ID da identidade gerenciada do container (variável AZURE_CLIENT_ID)"
  value       = azurerm_user_assigned_identity.visao.client_id
}

output "resource_group" {
  value = data.azurerm_resource_group.app.name
}
