# GS 2026.2 · CitizenTech · Ruas Escuras

Global Solution da FIAP · Engenharia de Software, 4º ano.
Um único produto que atravessa 7 disciplinas: cada integrante cuida de uma pasta.

## Ficha Técnica do MVP

| Campo | Conteúdo |
|---|---|
| **Nome do produto** | _a definir_ |
| **Cidadão e território** | Pedestres, ciclistas, motociclistas e moradores que circulam à noite em ruas com iluminação pública falha |
| **Problema, em uma frase** | Ruas escuras geram medo, assaltos e acidentes, e a falha demora a chegar à prefeitura porque depende de alguém reclamar |
| **Proposta de valor** | Ponte entre o cidadão e a prefeitura: o chamado chega confirmado, com localização, evidência e prioridade, e o cidadão acompanha até o conserto |
| **Arquitetura: componentes** | App do cidadão · Visão (YOLO26) · GenAI local · RPA · Big Data · robô com sensor de luz · deploy seguro ([docs/arquitetura.md](docs/arquitetura.md)) |
| **Fontes de dados** | Fotos do cidadão e do robô · datasets públicos de postes · dados abertos (SP156, Open-Meteo, IBGE) _a confirmar_ |
| **Modelos de IA utilizados** | YOLO26 (detecção de postes acesos/apagados) · LLM local com RAG _a definir_ |
| **URL do MVP e repositório** | _a definir_ · https://github.com/guilhermedaher10/Global-Solution_CitzenTech_2026 |
| **Indicadores de impacto** | Tempo da falha até o chamado · tempo até o conserto · % de chamados válidos · chamados por mil habitantes, centro × periferia |
| **ODS conectados** | 11, 3, 10 e 9 (detalhes abaixo) |

## Problema
Ruas com iluminação pública falha geram medo, aumentam o risco de assalto e causam acidentes
(quedas de pedestres, ciclistas e motociclistas). Isso afeta o bem-estar e a mobilidade das pessoas.
Além disso, a falha demora a chegar até a prefeitura, porque depende de alguém reclamar.

## Solução
Nós não consertamos o poste: somos a **ponte entre o cidadão e a prefeitura**.

- **Cidadão:** reporta a rua escura com uma foto (ou um robô com câmera e sensor de luz detecta sozinho) e acompanha o status até o conserto.
- **Prefeitura:** recebe o chamado já confirmado, com localização, evidência e prioridade.

## ODS
- **ODS 11:** cidades e comunidades sustentáveis
- **ODS 3:** saúde e bem-estar (acidentes)
- **ODS 10:** redução das desigualdades
- **ODS 9:** indústria, inovação e infraestrutura

## Integrantes

| Nome completo | RM | Disciplina |
|---|---|---|
| Guilherme Gonçalves Calil Daher | 98611 | Visão Computacional · DevOps e Cloud |
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
   - o título está no formato `pasta: descrição` (ex.: `rpa: fluxo de registro dos chamados`).
2. **Quem abriu o PR faz o merge** (botão **Squash and merge**). Não precisa de aprovação de outra pessoa, mas o robô precisa estar ✅.

Se o robô reprovar, abra a aba **Checks** do PR: o erro diz o arquivo e o que fazer. Corrija, dê push na mesma
branch e ele roda de novo sozinho.

- Mexa **só na sua pasta**. Mudança na raiz ou em `docs/` vai pela branch `docs-projeto`, avisando o grupo.
- Comece a mensagem do commit pelo nome da pasta (`rpa:`, `big-data:`, `visao:`...).
- Nunca commite senha, chave de API ou `.env`.
- Arquivos grandes (dataset, modelo pesado, vídeo) vão por link (Drive, YouTube), não para o Git.

**Entrega:** 19/11/2026, até 23h55. O repositório precisa estar público durante a correção.
