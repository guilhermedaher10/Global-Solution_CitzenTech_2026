# Arquitetura do produto (proposta para o grupo)

> Proposta inicial para discutir. Cada pessoa decide como fazer a sua parte. O que precisamos combinar são os
> **contratos** (o que cada componente entrega e consome), para tudo se encaixar no mesmo sistema.

## Fluxo

```
                ┌──────────────────────────── CIDADÃO ────────────────────────────┐
                │  App web (MVP, URL pública): foto + localização · acompanha status│
                └───────────────┬───────────────────────────────────▲───────────┘
                                │ foto                               │ status / respostas
                                ▼                                    │
 Robô Maker Lab ──foto+lux──► [04 VISÃO API] ──JSON──► [BACKEND DE CHAMADOS] ◄──► [01 GENAI]
 (câmera + LDR)               YOLO26 + regras          banco: chamados,         assistente local:
                                                       status, histórico        responde o cidadão e
                                                              │                 redige o chamado (RAG)
                                                              ▼
                                                   [05 RPA] fila priorizada:
                                                   agrupa duplicados, registra no
                                                   sistema da prefeitura, atualiza status
                                                              │
                                                              ▼
                                         PREFEITURA / CONCESSIONÁRIA: atendente confirma → conserto
                                                              │
 Fontes abertas ──► [02 BIG DATA] Airflow → Bronze/Prata/Ouro ◄┘ (chamados + capturas)
                    indicadores: tempo até conserto, trechos escuros, desigualdade por região
                                                              │
                         [03 NEGÓCIO] pitch, modelo de negócio e KPIs sobre a Ouro
                         [06 DEVOPS] tudo em container, Terraform, CI/CD seguro, Grafana
```

## Ciclo de vida do chamado
`recebido` → `validado` (Visão) → `confirmado` (atendente) → `encaminhado` (RPA) → `em_reparo` → `resolvido`,
ou `recusado` com motivo. O cidadão vê cada mudança no app.

## Componentes e contratos

| # | Componente | Entrega | Consome | Contrato |
|---|---|---|---|---|
| 04 | **Visão** | Validação da foto, status do trecho, prioridade | Foto, GPS, lux | `POST /v1/analisar` → JSON v1.0 ([detalhes](../04-visao-computacional/docs/integracao.md)) ✅ |
| 07 | **Maker Lab** | Robô com câmera + **sensor de luz (LDR)**: patrulha, mede lux e fotografa; reage ao resultado (LED/voz/alerta) | Resposta da Visão | Faz POST na API da Visão com `origem=robo` e `sensor_lux` |
| — | **Backend + app (MVP)** | Tela do cidadão (enviar foto, acompanhar) e do atendente (fila, confirmar) | Visão, GenAI | REST + banco (ex.: Postgres). **A definir quem faz** |
| 05 | **RPA** | Fluxo que pega chamados confirmados, agrupa duplicados por proximidade, registra no sistema da prefeitura (portal simulado ou SP156) e atualiza o status, com logs | Banco de chamados | Lê/escreve no banco ou na API do backend |
| 02 | **Big Data** | Pipeline Airflow → Databricks (Bronze/Prata/Ouro) com chamados + fontes abertas; tabela Ouro que o MVP mostra | Export dos chamados/capturas (JSON) + APIs abertas | Arquivos JSON por coleta na pasta `chegada/` |
| 01 | **GenAI** | LLM local com RAG sobre regras de iluminação pública, prazos e serviço 156: responde o cidadão e gera o texto formal do chamado em JSON, citando a fonte e recusando quando "não consta" | Base de documentos públicos + resumo da Visão | API própria (ex.: `POST /perguntar`) |
| 06 | **DevOps** | `docker compose` com tudo, Terraform, GitHub Actions (build, Gitleaks, Semgrep, Trivy), deploy, Grafana com as 4 métricas de ouro + alerta | Dockerfiles de cada componente | A Visão já tem `Dockerfile` e `GET /saude` ✅ |
| 03 | **Negócio** | Pitch de 5 min com o MVP real, modelo de negócio, KPIs e ODS | Ouro do Big Data, demo | — |

## Sugestões de fontes de dados abertas (Big Data e Negócio) — conferir disponibilidade
- **Solicitações do SP156** (portal de dados abertos da Prefeitura de SP): volume de reclamações de iluminação por bairro e tempo de atendimento. É a prova da dor.
- **Open-Meteo:** horário do pôr e do nascer do sol (de noite é quando a falha importa) e clima.
- **IBGE:** população por distrito/município (chamados por mil habitantes → desigualdade, ODS 10).
- **SSP-SP:** ocorrências criminais por região e período (correlação com trechos escuros, sem dado pessoal).
- **GeoSampa:** camadas de iluminação pública e logradouros, se disponíveis.

## Indicadores de impacto (para a Ficha Técnica e o pitch)
- Tempo entre a falha detectada e o chamado registrado (hoje: depende de reclamação)
- Tempo médio até o conserto, por região
- % de chamados válidos (a validação da Visão filtra foto de dia, duplicada etc.)
- Postes apagados por km percorrido pelo robô
- Chamados por mil habitantes, centro × periferia (ODS 10)

## Princípios (do PDF da GS) e como atendemos
| Princípio | Como |
|---|---|
| Segurança e LGPD by design | Visão borra rostos, descarta EXIF e não guarda imagem; Big Data mascara dados pessoais na Ouro; segredos fora do código |
| IA responsável | Decisões com motivos; atendente humano confirma antes do conserto; vieses documentados |
| Integração real | Contratos por API e banco (não prints lado a lado) |
| Resiliente | App aceita foto offline e envia depois; a API da Visão degrada com aviso (`/saude`) |
| Reprodutível | README + requirements + testes em cada pasta |
