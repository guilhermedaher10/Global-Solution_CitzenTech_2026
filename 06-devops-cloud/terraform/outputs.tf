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

output "resource_group" {
  value = data.azurerm_resource_group.app.name
}
