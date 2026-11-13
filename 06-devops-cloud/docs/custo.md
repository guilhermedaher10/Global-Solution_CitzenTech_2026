# Estimativa de custo (Azure, região East US)

> Preços de tabela públicos em US$ (pay-as-you-go), consultados em nov/2026. Câmbio de referência:
> **US$ 1 = R$ 5,50**. Confirme na [calculadora da Azure](https://azure.microsoft.com/pricing/calculator/):
> os valores mudam e a fatura real pode variar. A assinatura usada é **Azure for Students**
> (crédito pré-pago, **limite de gasto ligado**: quando o crédito acaba, os recursos param; não há cobrança).

## Preço de cada peça

| Recurso | Como cobra | Preço de tabela |
|---|---|---|
| Container Apps (consumo) | por segundo de vCPU e de GiB de memória | ativo: US$ 0,000024/vCPU·s e US$ 0,000003/GiB·s · ocioso (réplica parada esperando): US$ 0,000003/vCPU·s · **cota grátis mensal**: 180.000 vCPU·s, 360.000 GiB·s e 2 milhões de requisições |
| Container Registry Basic | por dia | ~US$ 0,167/dia (~US$ 5/mês) |
| Log Analytics | por GB ingerido | primeiros 5 GB/mês grátis; teto configurado de 0,5 GB/dia |
| Storage do state | por GB e operação | centavos (o state tem poucos KB) |
| Storage da central (Table, LRS) | por GB e por 10 mil transações | ~US$ 0,045/GB·mês e ~US$ 0,00036/10 mil operações: centavos (cada chamado tem ~2 KB) |
| Orçamento, identidade, OIDC | — | grátis |

## Cenários (Visão com 1 vCPU e 2 GiB por réplica)

| Cenário | Conta | US$/mês | R$/mês |
|---|---|---|---|
| **A. Dorme sem uso** (`visao_min_replicas = 0`, padrão), ~1.000 análises/mês de ~2 s | 2.000 vCPU·s ativos: dentro da cota grátis. Sobra o ACR | **~5** | **~28** |
| **B. Sempre acordada** (`= 1`), ociosa a maior parte do tempo | 2,59 M s × (1 × 0,000003 + 2 × 0,000003) ≈ US$ 23, menos a cota grátis ≈ US$ 22, + ACR | **~27** | **~150** |
| **B'. Sempre acordada com 0,5 vCPU / 1 GiB** | metade do B + ACR | **~16** | **~90** |

**Estratégia do projeto:** cenário A o tempo todo; cenário B só na semana da demonstração/coleta de evidências
(o Prometheus lendo a nuvem a cada 15 s também mantém a réplica acordada). Até a entrega (~3 semanas):
**~R$ 55** (3 semanas de ACR + 1 semana acordada), cerca de 10% do crédito disponível.

## Proteções contra gasto inesperado
1. **Escala a zero** por padrão (`visao_min_replicas = 0`) e **teto de réplicas** (`visao_max_replicas = 2`).
2. **Orçamento** `orcamento-ruasescuras` (Terraform): e-mail em 50%, 80% e 100% do valor real e em 100% do **previsto**.
3. **Cota diária** de 0,5 GB no Log Analytics.
4. **Desligar tudo** depois da avaliação: `terraform destroy` (ver README). O bootstrap (state e identidade) sai com
   `az group delete -n rg-ruasescuras-tfstate`.
