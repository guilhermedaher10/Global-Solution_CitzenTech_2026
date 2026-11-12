variable "resource_group" {
  description = "Grupo da aplicação, criado pelo bootstrap (o robô do pipeline só tem permissão nele)"
  type        = string
  default     = "rg-ruasescuras"
}

variable "prefixo" {
  description = "Prefixo dos nomes dos recursos"
  type        = string
  default     = "ruasescuras"
}

variable "visao_min_replicas" {
  description = "0 = dorme sem uso (custo ~zero, 1ª foto demora ~30 s para acordar); 1 = sempre acordada (demo)"
  type        = number
  default     = 0

  validation {
    condition     = var.visao_min_replicas >= 0 && var.visao_min_replicas <= 2
    error_message = "Use 0, 1 ou 2."
  }
}

variable "visao_max_replicas" {
  description = "Teto de réplicas: limita o custo mesmo sob muito acesso"
  type        = number
  default     = 2
}

variable "visao_imagem_inicial" {
  description = "Imagem só da CRIAÇÃO do app; depois a versão em produção é do pipeline (ignore_changes)"
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "visao_cpu" {
  description = "vCPU por réplica (Container Apps aceita pares cpu/memória fixos: 1.0 -> 2Gi)"
  type        = number
  default     = 1.0
}

variable "visao_memoria" {
  type    = string
  default = "2Gi"
}

variable "orcamento_mensal" {
  description = "Orçamento do grupo, na moeda da assinatura; alerta por e-mail em 50/80/100%"
  type        = number
  default     = 100
}

variable "emails_alerta" {
  description = "Quem recebe os alertas de custo. Dado pessoal: passe por TF_VAR_emails_alerta / tfvars (fora do Git)"
  type        = list(string)
  sensitive   = true
}

variable "inicio_orcamento" {
  description = "Primeiro dia do mês em que o orçamento começa (exigência da Azure)"
  type        = string
  default     = "2026-11-01T00:00:00Z"
}

variable "tags" {
  type = map(string)
  default = {
    projeto        = "ruas-escuras"
    curso          = "fiap-gs-2026-2"
    gerenciado-por = "terraform"
  }
}
