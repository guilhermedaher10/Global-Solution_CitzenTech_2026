# Arquitetura do Vésper

> Como o produto ficou, com cada componente das 7 disciplinas e os **contratos** que os ligam (API, arquivos, banco).
> MVP público: https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io

## Fluxo

```
  CIDADÃO (site, URL pública)                          ROBÔ DO MAKER LAB (07)
  foto · vídeo 10 s · relato sem foto                  ESP32 + LDR + ultrassom + GPS + TinyML 4→12→4
        │ POST /v1/analisar · /v1/analisar-video          │ escuro_* confirmado → POST /v1/alerta-robo
        │ POST /v1/relatos                                │ (firmware Vesper.h · gêmeo digital · aba Robô)
        ▼                                                 ▼
 ┌──────────────────────────── [04 VISÃO · API do Vésper] ─────────────────────────────┐
 │ YOLO26 (poste aceso/apagado, buraco) + análise de cena (breu, apagão) + fusão sensor  │
 │ prioridade explicável · borra rostos · descarta EXIF · não guarda imagem              │
 │ CENTRAL DE CHAMADOS: /v1/chamados (Azure Table na nuvem, SQLite local)                 │──GENAI_URL──► [01 GENAI]
 └──────┬───────────────────────────────┬───────────────────────────────▲──────────────┘   RAG local (Ollama):
        │ GET /v1/chamados               │ site: Central (fila + mapa),    │                   prazo e canal oficial
        ▼                                │ Acompanhar (linha do tempo)     │ GET /v1/indicadores  com a fonte citada
 [05 RPA] RPA_FONTE=api                  │                                 │
 agrupa duplicados · PDF do chamado ·    │                    [02 BIG DATA] Airflow (SP156, Open-Meteo, IBGE)
 e-mail / portal (UiPath) · n8n          │                    → Databricks Bronze → Prata → Ouro
 POST /v1/chamados/{p}/status ───────────┘                    → ouro_mvp_mapa → aba Indicadores do site
 → "encaminhado" na linha do tempo
                                                              [03 NEGÓCIO] pitch e KPIs sobre a Ouro + demo
 [06 DEVOPS] container · Terraform (Azure) · GitHub Actions (Gitleaks, Semgrep, Trivy, plan/apply, deploy) · Prometheus/Grafana
```

## Ciclo de vida do chamado (central da Visão)

`suspeita` (robô ou relato sem foto) **ou** `recebido` (foto validada pela IA) → `confirmado` (atendente na Central) →
`encaminhado` (RPA) → `em_reparo` → `resolvido`, ou `recusado`. A central não deixa pular etapa, e o cidadão vê cada
mudança em **Acompanhar** pelo protocolo `VSP-XXXXXX`.

## Componentes e contratos

| # | Componente | O que faz | Contrato | Situação |
|---|---|---|---|---|
| 04 | **Visão** (API + site) | Valida a foto, mede a cena, detecta postes e buracos, calcula a prioridade e mantém a **central de chamados** | `POST /v1/analisar`, `/v1/analisar-video`, `/v1/relatos`, `/v1/alerta-robo`; `GET/POST /v1/chamados`; `GET /v1/regioes`; `GET /v1/indicadores` (contrato 1.5, [detalhes](../04-visao-computacional/docs/integracao.md)) | ✅ No ar na Azure |
| 07 | **Maker Lab** | Carrinho que patrulha e classifica `claro/escuro × livre/obstáculo` com TinyML embarcado | `POST /v1/alerta-robo` com `classe_ia` e `confianca_ia`; a API devolve a prioridade e o LED (`acao_robo`). Escuro + obstáculo = alta | ✅ Firmware compila. A integração é demonstrada pelo **gêmeo digital** (`07-maker-lab/ia/gemeo_digital.py`) e pela **aba Robô**, que rodam os mesmos pesos (`ModeloTreinado.h`). Não foi testada no carrinho físico |
| 05 | **RPA** | Pega chamados `confirmado`, agrupa os do mesmo trecho, gera o PDF, registra (e-mail, ou portal via UiPath) e avisa o n8n | `RPA_FONTE=api`: `GET /v1/chamados` → `POST /v1/chamados/{protocolo}/status` (`encaminhado` + protocolo da prefeitura). `csv` continua como modo offline | ✅ |
| 02 | **Big Data** | Coleta diária no Airflow e pipeline Bronze → Prata → Ouro no Databricks (968 mil linhas em 2 lotes → 303 mil chamados válidos → 1.113 de poste e fiação em 95 distritos) | Ouro (`ouro_mvp_mapa` + 5 consultas) → `scripts/exportar_ouro_web.py` → `GET /v1/indicadores` → aba **Indicadores** | ✅ Os números vêm do notebook executado e de `amostras/ouro_mvp_mapa.json` (tabela completa, com o mapa por distrito) |
| 01 | **GenAI** | LLM local com RAG sobre as regras de iluminação pública e o serviço 156: prazo e canal oficial, citando a fonte e recusando quando "não consta" | A Visão chama a GenAI (`GENAI_URL`) quando a análise abre um chamado e anexa a orientação ao resultado | ✅ Via `docker compose` (Ollama). **Não está na Azure:** sem GPU, ~1 min por resposta |
| 06 | **DevOps** | Imagem da Visão, infraestrutura e entrega contínua com segurança | Terraform: ACR, Container Apps, identidade gerenciada, Storage (Table da central), Log Analytics, orçamento. Actions: Gitleaks, Semgrep, Trivy, `terraform plan/apply`, deploy com smoke test. `/metrics` → Prometheus/Grafana | ✅ |
| 03 | **Negócio** | Pitch de 5 min com o MVP real, modelo de negócio e KPIs | Números da Ouro (Indicadores) e demo ao vivo | Vídeo |

## O que é integração real (e o que não é)

- **Por API:** o robô e o site alimentam a central; o RPA lê e escreve nela; o site lê a Ouro; a Visão chama a GenAI.
- **Por arquivo versionado:** a IA do carrinho vai para o site (`tinyml-carrinho.json`, gerado do firmware) e a Ouro vai para o site (`ouro-bigdata.json`, gerado do Databricks). Testes falham se esses arquivos ficarem diferentes da origem.
- **Decisões conscientes:**
  - Os chamados do Vésper **não são somados** aos do SP156 na Ouro: o SP156 é o histórico oficial da cidade, e o Vésper é o produto funcionando agora. Os dois aparecem lado a lado na aba Indicadores.
  - A GenAI roda local por custo.
  - O carrinho físico não foi remontado; a integração usa o gêmeo digital, com o mesmo modelo e o mesmo contrato.

## Indicadores de impacto

- **Da cidade (Big Data, SP156 jul–set/2026):**
  - 1.113 chamados de poste e fiação (o SP156 não tem o serviço "lâmpada apagada");
  - 18,1 dias em média até fechar o chamado (mediana de 11; 10% passam de 41);
  - 62,6% dos chamados do SP156 passam nas 3 regras de qualidade da Prata;
  - o Centro tem 1,7× mais chamados por 100 mil habitantes que a Periferia (16,3 × 9,5).
- **Do produto (central ao vivo):** chamados por origem (foto, robô, relato), por prioridade e por situação.

## Princípios da GS e como atendemos

| Princípio | Como |
|---|---|
| Segurança e LGPD by design | A Visão borra rostos, descarta EXIF e não guarda imagem; a Ouro só tem agregados (endereço em hash); segredos fora do código (Gitleaks no CI) |
| IA responsável | Decisões com motivos e fatores; o atendente humano confirma antes de encaminhar; a GenAI cita a fonte ou recusa; limitações documentadas em cada pasta |
| Integração real | Contratos por API e por arquivos com teste de consistência, não prints lado a lado |
| Resiliente | A API degrada com aviso (`/saude`); a central fora do ar não derruba a análise; o carrinho funciona sem internet; o RPA reenvia o que falhou |
| Reprodutível | README + requirements + testes em cada pasta; CI roda os testes de cada pasta alterada |
