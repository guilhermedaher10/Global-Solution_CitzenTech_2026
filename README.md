# Vésper · da escuridão à luz

**GS 2026.2 · CitizenTech · tema Ruas Escuras** · FIAP · Engenharia de Software, 4º ano.
Um único produto que atravessa 7 disciplinas: cada integrante cuida de uma pasta.

🌐 **MVP no ar:** https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io
(API documentada em [`/docs`](https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io/docs))

## Ficha Técnica do MVP

| Campo | Conteúdo |
|---|---|
| **Nome do produto** | **Vésper**: o nome da "estrela" que aparece logo depois que escurece. A ponte entre a rua escura e quem pode acendê-la |
| **Cidadão e território** | Pedestres, ciclistas, motociclistas e moradores que circulam à noite em ruas com iluminação pública falha ou em bairros sem energia, com foco nas periferias das metrópoles, onde a falha demora mais para ser consertada |
| **Problema, em uma frase** | Ruas escuras geram medo, assaltos e acidentes, e a falha demora a chegar à prefeitura ou à distribuidora de energia porque depende de alguém reclamar, no canal certo, com informação suficiente |
| **Proposta de valor** | O cidadão aponta o celular para a rua e, em segundos, o chamado chega **confirmado por IA**, com localização, evidência, prioridade e **ao responsável certo** (poste apagado vai para a iluminação pública; apagão vai para a distribuidora de energia). O cidadão acompanha até o conserto. Sem cadastro, sem guardar a foto |
| **Arquitetura: componentes** | App web Vésper (cidadão, acompanhamento e central de chamados) · API de Visão (YOLO26 + análise de cena) · assistente GenAI local com RAG · robô Maker Lab com sensores de luz e distância · RPA que despacha os chamados · pipeline de Big Data · deploy na Azure com Terraform, CI/CD seguro e observabilidade ([docs/arquitetura.md](docs/arquitetura.md)) |
| **Fontes de dados** | Fotos do cidadão e do robô (analisadas e descartadas) · datasets públicos de postes no Roboflow Universe (licença CC BY 4.0) e imagens Openverse/Wikimedia com autor e licença registrados ([dataset](04-visao-computacional/docs/dataset.md)) · 135 fotos noturnas próprias, revisadas pela equipe · 31 trechos de fontes oficiais sobre iluminação pública (base do RAG) · dados abertos (SP156, IBGE, Open-Meteo) no Big Data |
| **Modelos de IA utilizados** | **YOLO26s** treinado por nós (postes acesos e apagados) · análise de cena explicável (índice de escuridão, fontes de luz, possível apagão) · YuNet (borrar rostos, LGPD) · **qwen2.5:1.5b-instruct** + embeddings **nomic-embed-text** via Ollama (RAG local, com citação e recusa) |
| **URL do MVP e repositório** | https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io · https://github.com/guilhermedaher10/Global-Solution_CitzenTech_2026 |
| **Indicadores de impacto** | Tempo da falha até o chamado · tempo até o conserto · % de chamados válidos (a IA filtra foto de dia, repetida ou sem evidência) · chamados encaminhados ao responsável certo · chamados por mil habitantes, centro × periferia |
| **ODS conectados** | 11, 3, 10, 9 e 16 (explicação abaixo) |

## Problema
Ruas com iluminação pública falha geram medo, aumentam o risco de assalto e causam acidentes
(quedas de pedestres, ciclistas e motociclistas). Quando falta energia no bairro, o breu é total.
A falha demora a chegar a quem conserta, porque depende de alguém reclamar, saber **para quem** reclamar
(prefeitura ou distribuidora de energia) e descrever o local direito.

## Solução
Nós não consertamos o poste: somos a **ponte entre o cidadão e quem pode acender a rua**.

- **Cidadão:** abre o site (inclusive pelo **QR Code** colado em pontos da cidade), fotografa ou filma a rua
  **ao vivo** pelo próprio navegador, ou só informa o endereço quando está tudo escuro. Recebe um protocolo e
  acompanha o status.
- **IA (Visão):** encontra os postes acesos e apagados, mede o quanto a cena está escura e reconhece sinais de
  **apagão** (nenhuma luz, nem janelas, nem letreiros). Explica cada decisão.
- **Robô (Maker Lab):** patrulha com sensores de luz e distância e dispara alertas; a foto confirma.
- **Central:** a prefeitura ou a distribuidora recebe o chamado já confirmado, priorizado e com evidência;
  muitos relatos próximos viram um único alerta de região.
- **GenAI:** orienta o cidadão com base em fontes oficiais (prazos, canais), citando a fonte.
- **RPA:** despacha os chamados confirmados para o sistema de quem conserta e devolve o protocolo.

## ODS: como o Vésper contribui
| ODS | Contribuição concreta |
|---|---|
| **11 · Cidades e comunidades sustentáveis** (meta 11.7: espaços públicos seguros e inclusivos) | Encurta o tempo entre a rua apagar e o conserto, e mostra no mapa onde a cidade está no escuro |
| **3 · Saúde e bem-estar** (meta 3.6: reduzir mortes e lesões no trânsito) | Rua iluminada reduz atropelamentos, quedas e acidentes de moto e bicicleta à noite; trechos com buraco e sem luz ganham prioridade |
| **10 · Redução das desigualdades** (meta 10.2: inclusão de todos) | Basta um celular simples e um navegador, sem cadastro e sem app para instalar; o indicador "chamados por mil habitantes, centro × periferia" expõe onde o conserto demora mais |
| **9 · Indústria, inovação e infraestrutura** (meta 9.1: infraestrutura resiliente) | Visão computacional, sensores e automação transformam relatos soltos em dados confiáveis para a manutenção da rede |
| **16 · Paz, justiça e instituições eficazes** (meta 16.6: instituições eficazes e transparentes) | O cidadão acompanha cada etapa do chamado com protocolo, e o encaminhamento vai direto ao órgão responsável |

## IA responsável
- **Explica:** toda análise traz os motivos em português (quantos postes, quão escura, por que é ou não apagão).
- **Pessoa no circuito:** a IA sugere; o atendente da central confirma, encaminha ou recusa.
- **Privacidade (LGPD):** a foto não é guardada, rostos são borrados, os metadados (EXIF) são descartados.
- **Vieses conhecidos:** a maior parte dos datasets públicos de postes é de ruas asiáticas e europeias; por isso
  incluímos fotos noturnas próprias de São Paulo e medimos o desempenho separado por cenário
  ([relatório da Visão](04-visao-computacional/docs/relatorio.md)).

## Integrantes

| Nome completo | RM | Disciplina |
|---|---|---|
| Guilherme Daher | 98611 | Visão Computacional · DevOps e Cloud |
| Gabriel Freitas | 550187 | Generative AI |
| Heitor Nobre | 551539 | Maker Lab |
| Vinicius Yamashita | 550908 | RPA |
| Lucca Alexandre | 99700 | Big Data · Negócio e Pitch |

> ⚠️ Vários professores tiram nota se faltar **nome completo** ou RM. Cada um confira e complete o seu nome.

## Pastas

| Pasta | Disciplina |
|---|---|
| `01-generative-ai/` | Generative AI |
| `02-big-data/` | Big Data |
| `03-negocio-pitch/` | Negócio e Pitch |
| `04-visao-computacional/` | Visão Computacional |
| `05-rpa/` | RPA |
| `06-devops-cloud/` | DevOps e Cloud |
| `docs/` | Arquitetura e contratos entre os componentes (do grupo todo) |
| `07-maker-lab/` | Maker Lab |

## Como cada um trabalha (branches)

**Ninguém commita direto na `main`.** Cada disciplina tem a sua branch, com o mesmo nome da pasta:

| Pasta | Branch |
|---|---|
| `01-generative-ai/` | `01-generative-ai` |
| `02-big-data/` | `02-big-data` |
| `03-negocio-pitch/` | `03-negocio-pitch` |
| `04-visao-computacional/` | `04-visao-computacional` |
| `05-rpa/` | `05-rpa` |
| `06-devops-cloud/` | `06-devops-cloud` |
| `07-maker-lab/` | `07-maker-lab` |
| raiz e `docs/` (do grupo) | `docs-projeto` |

```bash
# primeira vez
git clone https://github.com/guilhermedaher10/Global-Solution_CitzenTech_2026.git
cd Global-Solution_CitzenTech_2026
git checkout -b 05-rpa              # crie a branch da sua matéria (só na primeira vez)

# no dia a dia
git checkout 05-rpa
git pull origin main                # traz o que os outros já juntaram na main
# trabalhe só dentro da pasta da sua disciplina
git add 05-rpa/
git commit -m "rpa: primeira versão"
git push -u origin 05-rpa
```

Quando uma parte estiver pronta, abra um **Pull Request** da sua branch para a `main` no GitHub.
O merge só libera quando:

1. **O robô aprova** (GitHub Actions `pr-validacao`). Ele confere:
   - o nome da branch está na tabela acima;
   - o PR só mexe na pasta da própria matéria;
   - não tem senha ou chave vazada (Gitleaks);
   - não tem `.env`, vídeo, state do Terraform nem arquivo acima de 10 MB;
   - o Python não tem erro de sintaxe nem nome indefinido;
   - os **testes automatizados** de cada pasta alterada passam (`tests/` com pytest + `requirements.txt` na pasta da matéria);
   - o título está no formato `pasta: descrição` (ex.: `rpa: fluxo de registro dos chamados`).
2. **Quem abriu o PR faz o merge** (botão **Squash and merge**). Não precisa de aprovação de outra pessoa, mas o robô precisa estar ✅.

Se o robô reprovar, abra a aba **Checks** do PR: o erro diz o arquivo e o que fazer. Corrija, dê push na mesma
branch e ele roda de novo sozinho.

- Mexa **só na sua pasta**. Mudança na raiz ou em `docs/` vai pela branch `docs-projeto`, avisando o grupo.
- Comece a mensagem do commit pelo nome da pasta (`rpa:`, `big-data:`, `visao:`...).
- Nunca commite senha, chave de API ou `.env`.
- Arquivos grandes (dataset, modelo pesado, vídeo) vão por link (Drive, YouTube), não para o Git.

**Entrega:** 19/11/2026, até 23h55. O repositório precisa estar público durante a correção.
