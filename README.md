# RPA

**Professores:** Bruno Diniz e Cibele Ribeiro

**Responsável:** Vinicius Yamashita · RM 550908

**Vídeo (até 3 min):** _(link do YouTube)_

## Despachante de chamados de iluminação

Robô da CitizenTech para o tema **ruas escuras priorizadas por risco**. A Visão valida a foto e calcula a prioridade, o atendente confirma o chamado, e este robô faz o resto: agrupa os duplicados por proximidade, gera o chamado, registra na prefeitura e passa o status para `encaminhado`, com log de tudo.

### Onde ele entra na arquitetura

Componente **05 RPA** de [`docs/arquitetura.md`](../docs/arquitetura.md). Consome o JSON da Visão (contrato v1.1, em [`04-visao-computacional/docs/integracao.md`](../04-visao-computacional/docs/integracao.md)) e segue o ciclo de vida do chamado do grupo:

`recebido` → `validado` (Visão) → `confirmado` (atendente) → **`encaminhado` (RPA)** → `em_reparo` → `resolvido`

```
Visão (JSON v1.1) -> chamados `validado` -> atendente confirma -> ROBÔ (esta pasta) -> prefeitura (e-mail ou portal)
                                                                    |                      |
                                                                    |                      +-> UiPath preenche o portal
                                                                    +-> n8n avisa por e-mail (resumo e chamados aguardando o atendente)
                                                                    +-> grava status `encaminhado` + protocolo -> app do cidadão
```

| Peça | Papel |
|---|---|
| **Python** (`src/`) | Núcleo: lê os chamados confirmados, valida, agrupa por proximidade, gera o PDF, registra, loga e grava o status |
| **UiPath** (`uipath/`) | Preenche o portal da prefeitura e devolve o protocolo (modo `portal`) |
| **n8n** (`n8n/`) | Recebe o resumo da execução e avisa por e-mail, destacando os chamados que ainda aguardam o atendente |

Fluxo, regras de negócio, exceções e LGPD em [`docs/PDD.md`](docs/PDD.md).

### O que o robô faz com cada chamado

1. **Pega** só os `confirmado` (o atendente já decidiu).
2. **Valida** id, coordenadas, foto e prioridade. Se faltar algo, marca `falha_dados` com o motivo e segue.
3. **Agrupa duplicados por proximidade**: até 30 m e ao menos um tipo de chamado em comum. Poste apagado e buraco na mesma rua vão para setores diferentes e não se juntam. Se já existe um chamado do trecho encaminhado nos últimos 30 dias, o novo é anexado a ele.
4. **Ordena** pela pontuação da Visão (`prioridade.pontuacao`) e **encaminha** um chamado por grupo, com prazo sugerido pelo nível (alta 48 h, média 7 dias, baixa 15 dias).
5. **Registra** por e-mail ou pela fila do portal, grava `encaminhado` + protocolo (os agrupados recebem o mesmo) e manda o resumo ao n8n.

### Estrutura

```
src/            código Python
  main.py         orquestra o fluxo (loop, decisões, tratamento de exceção)
  contrato.py     contrato com a Visão (JSON v1.1) e ciclo de vida do chamado
  regras.py       validação dos dados
  agrupamento.py  duplicados por proximidade (haversine + tipo em comum)
  chamado.py      PDF do chamado       envio.py     e-mail / portal, com retry
  anonimizacao.py LGPD da foto         notificacao.py  resumo para o n8n
  repositorio.py  leitura/escrita da tabela (troca para o backend aqui)
  logger.py       robo.log e auditoria.csv        config.py  parâmetros e .env
data/           chamados.csv (simula o banco de chamados), visao_exemplos.jsonl (JSON v1.1) e fotos/ sintéticas
tests/          46 testes: sucesso, decisão e falha
docs/           PDD.md (fluxo, regras, contrato)
logs/, outbox/  saídas geradas a cada execução (não versionadas)
uipath/         guia para montar o fluxo no UiPath Studio (o projeto exportado vai aqui)
n8n/            workflow_despachante.json (importar no n8n)
portal_mock/    portal de zeladoria SIMULADO para a demonstração
scripts/        importar_visao.py, resetar_demo.py, gerar_fotos_exemplo.py
```

### Como rodar

Execute a partir da pasta `05-rpa/`, um comando por vez (no PowerShell antigo `&&` não funciona):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m pytest -q
python -m src.main --dry-run
python -m src.main
```

No Linux/macOS, use `source .venv/bin/activate` e `cp .env.example .env`.

- `--dry-run`: só decide e registra no log, sem enviar, sem alterar a tabela e sem avisar o n8n.
- `python scripts/resetar_demo.py`: reconstrói a tabela de exemplo para repetir a demonstração. O robô só processa chamados `confirmado`, então uma segunda execução sem reset não reenvia nada.
- `python scripts/importar_visao.py <arquivo.jsonl>`: converte respostas da Visão em chamados (`--confirmar` simula o atendente). Aceita um `.json`, um `.jsonl` (como o gerado por `tempo_real.py --eventos` da Visão) ou uma pasta.

### Modos de envio (`ENVIO_MODO` no `.env`)

| Modo | O que faz | Quando usar |
|---|---|---|
| `mock` | Grava o e-mail como `.eml` em `outbox/emails/` | Padrão e demonstração (seguro) |
| `smtp` | Envia e-mail de verdade | Só com uma caixa de **teste** |
| `portal` | Gera `outbox/fila_portal.csv` para o UiPath | Demonstração com UiPath |

> Não aponte o robô para um e-mail ou portal real de prefeitura durante a demonstração. A troca para o canal real é só configuração.

**Fluxo com o portal:** `ENVIO_MODO=portal` → `python -m src.main` → UiPath preenche o portal ([guia](uipath/GUIA_UIPATH.md)) → `python -m src.main --sincronizar-protocolos` passa os chamados para `encaminhado` com o protocolo.

### n8n

1. Importe `n8n/workflow_despachante.json`, conecte a credencial do Gmail (OAuth2) nos dois nós de e-mail e troque `SEU_EMAIL@exemplo.com` pelo destinatário.
2. Ative o workflow e coloque a URL de produção do webhook em `N8N_WEBHOOK_URL` no `.env`.
3. A cada execução o robô envia o resumo. Se houver chamados `validado` esperando o atendente, o e-mail os lista.

### Dados de exemplo

`data/visao_exemplos.jsonl` tem 12 respostas **sintéticas** da Visão (formato v1.1), e `data/chamados.csv` é a tabela gerada a partir delas. Elas exercitam todos os caminhos:

| ID | Situação | Resultado esperado |
|---|---|---|
| C-000 | já encaminhado em 28/10 | só serve de referência para o agrupamento |
| C-001 | poste apagado, prioridade alta (90) | encaminhado; consolida C-002 |
| C-002 | a 11 m de C-001, mesmo tipo | agrupado em C-001 |
| C-003 | outro ponto, prioridade média (50) | encaminhado |
| C-004 | instalação de iluminação, baixa (15) | encaminhado |
| C-005 | poste apagado + buraco, alta (100) | encaminhado primeiro; consolida C-006 |
| C-006 | buraco a 11 m de C-005 | agrupado em C-005 (tipo `buraco` em comum) |
| C-007 | poda/obstrução a 11 m de C-001 | **não** agrupa: setor diferente; encaminhado |
| C-008 | sem coordenada | `falha_dados` |
| C-009 | sem foto | `falha_dados` |
| C-010 | a 11 m de C-000, que já foi encaminhado | anexado a C-000, sem chamado novo |
| C-011 | `validado`, falta o atendente | não processado; o n8n avisa |

Resumo esperado da primeira execução: 10 processados, 5 encaminhados (2 alta, 2 média, 1 baixa), 3 agrupados, 2 falhas de dados, 1 aguardando o atendente.

### Segurança e LGPD

- Segredos só em `.env` (fora do Git). O repositório não contém chaves nem dados pessoais reais.
- A Visão já borra rostos e remove o EXIF. O robô reencoda a foto (remove EXIF e GPS de novo) e, com `pip install -r requirements-opcional.txt` e as cascatas do OpenCV disponíveis, desfoca rostos e placas como segunda barreira; sem isso, avisa no log.
- A auditoria registra só IDs, ação e resultado.

### Contrato com o grupo e pendências

| Contrato (`docs/arquitetura.md`) | Situação |
|---|---|
| Consome o JSON da Visão v1.1 | feito (`src/contrato.py`, `scripts/importar_visao.py`) |
| Pega `confirmado` e passa para `encaminhado` | feito |
| Agrupa duplicados por proximidade | feito (raio e janela configuráveis) |
| Registra no sistema da prefeitura (portal simulado) | feito (e-mail ou portal mock com UiPath); SP156 real não está integrado |
| Lê/escreve no banco ou na API do backend | **pendente**: o backend ainda não foi definido. Hoje o CSV faz esse papel e só `ler` e `salvar` em `src/repositorio.py` precisam trocar |
| Texto formal do chamado pela GenAI | **pendente**: a GenAI ainda só responde perguntas (`POST /consulta`); o PDF usa um texto-base próprio (`src/config.py`) |
