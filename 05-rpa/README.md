# RPA

**Professores:** Bruno Diniz e Cibele Ribeiro

**Responsável:** Vinicius Yamashita · RM 550908

**Vídeo (até 3 min):** _(link do YouTube)_

## Despachante de chamados de iluminação

Robô da CitizenTech para o tema **ruas escuras priorizadas por risco**. A IA do produto detecta o poste apagado; este robô pega a ocorrência já classificada, decide o que fazer com ela, gera o chamado e o envia a quem conserta, sem intervenção humana, exceto quando a IA não tem certeza.

### Onde ele entra na arquitetura

Componente **05 RPA** de [`docs/arquitetura.md`](../docs/arquitetura.md): consome as ocorrências validadas pela Visão (04) e registradas no banco, e devolve status e protocolo para o MVP mostrar ao cidadão.

```
Maker Lab / Visão / GenAI -> tabela de ocorrências -> ROBÔ (esta pasta) -> prefeitura (e-mail ou portal)
                                                        |                       |
                                                        |                       +-> UiPath preenche o portal
                                                        +-> n8n avisa por e-mail (resumo e revisão humana)
                                                        +-> grava status/protocolo de volta -> MVP
```

| Peça | Papel |
|---|---|
| **Python** (`src/`) | Núcleo: lê a tabela, aplica regras, gera PDF, envia, loga e grava o status |
| **UiPath** (`uipath/`) | Preenche o portal da prefeitura e devolve o protocolo (modo `portal`) |
| **n8n** (`n8n/`) | Recebe o resumo da execução e avisa por e-mail, destacando itens que pedem revisão humana |

Fluxo, regras de negócio, exceções e LGPD em [`docs/PDD.md`](docs/PDD.md).

### Estrutura

```
src/            código Python (main, regras, chamado, envio, anonimizacao, notificacao, logger, repositorio, config)
data/           ocorrencias.csv (simula a tabela de ocorrências) e fotos/ (sintéticas)
tests/          18 testes: sucesso, decisão e falha
docs/           PDD.md (fluxo + regras) e exemplo_resultado_ocorrencias.csv
logs/           robo.log e auditoria.csv (gerados a cada execução, não versionados)
outbox/         e-mails .eml, PDFs de chamado e fila do portal (gerados, não versionados)
uipath/         guia para montar o fluxo no UiPath Studio
n8n/            workflow_despachante.json (importar no n8n)
portal_mock/    portal de zeladoria SIMULADO para a demonstração
scripts/        gerar_fotos_exemplo.py e resetar_demo.py
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

- `--dry-run`: só decide e registra no log, sem enviar nem alterar a tabela.
- `python scripts/resetar_demo.py`: devolve a tabela de exemplo ao estado inicial para repetir a demonstração. O robô só processa ocorrências `PENDENTE` ou `APROVADO`, então uma segunda execução sem reset não reenvia nada.

### Modos de envio (`ENVIO_MODO` no `.env`)

| Modo | O que faz | Quando usar |
|---|---|---|
| `mock` | Grava o e-mail como `.eml` em `outbox/emails/` | Padrão e demonstração (seguro) |
| `smtp` | Envia e-mail de verdade | Só com uma caixa de **teste** |
| `portal` | Gera `outbox/fila_portal.csv` para o UiPath | Demonstração com UiPath |

> Não aponte o robô para um e-mail ou portal real de prefeitura durante a demonstração. A troca para o canal real é só configuração.

**Fluxo com o portal:** `ENVIO_MODO=portal` → `python -m src.main` → UiPath preenche o portal ([guia](uipath/GUIA_UIPATH.md)) → `python -m src.main --sincronizar-protocolos` marca os itens como `PROTOCOLADO`.

### n8n

1. Importe `n8n/workflow_despachante.json`, conecte a credencial do Gmail (OAuth2) nos dois nós de e-mail e troque `SEU_EMAIL@exemplo.com` pelo destinatário.
2. Ative o workflow e coloque a URL de produção do webhook em `N8N_WEBHOOK_URL` no `.env`.
3. A cada execução o robô envia o resumo; se houver itens em `REVISAO_HUMANA`, o e-mail destaca isso.

Para liberar um item revisado, troque o status dele para `APROVADO` e rode o robô de novo.

### Dados de exemplo

`data/ocorrencias.csv` tem 11 linhas **sintéticas** que exercitam todos os caminhos:

| ID | Caso | Resultado esperado |
|---|---|---|
| O-001 | normal | ENVIADO / NORMAL |
| O-002 | escola próxima | ENVIADO / URGENTE |
| O-003 | escuridão severa | ENVIADO / URGENTE |
| O-004 | mesmo poste de chamado antigo | DESCARTADO_DUPLICADO |
| O-005 | sem coordenada | FALHA_DADOS |
| O-006 | confiança 0,55 | REVISAO_HUMANA |
| O-007 | foto inexistente | FALHA_DADOS |
| O-008 | mesmo poste de O-001 no mesmo lote | DESCARTADO_DUPLICADO |
| O-009 | ponto de ônibus próximo | ENVIADO / URGENTE |
| O-010 | confiança baixa, já aprovada por humano | ENVIADO / NORMAL |

Resultado de referência em `docs/exemplo_resultado_ocorrencias.csv`.

### Segurança e LGPD

- Segredos só em `.env` (fora do Git). O repositório não contém chaves nem dados pessoais reais.
- A foto do chamado é reencodada, o que remove EXIF e GPS. Com `pip install -r requirements-opcional.txt` e as cascatas do OpenCV disponíveis, rostos e placas também são desfocados; sem isso, o robô avisa no log. O mais robusto é a Visão (04) já entregar a foto anonimizada.
- A auditoria registra só IDs, ação e resultado.

### Pendências de integração com o grupo

Hoje o robô roda sobre uma tabela simulada. Para se encaixar no contrato de [`docs/arquitetura.md`](../docs/arquitetura.md) falta alinhar:

| Arquitetura do grupo | Este robô hoje |
|---|---|
| Pega chamados `confirmado` e passa para `encaminhado` | Processa `PENDENTE`/`APROVADO` e grava `ENVIADO`/`FILA_PORTAL`/`PROTOCOLADO` |
| Agrupa duplicados por **proximidade** | Duplicidade pelo mesmo `poste_id` em 30 dias |
| Lê/escreve no banco ou na API do backend | Lê/escreve `data/ocorrencias.csv`; a troca fica só em `src/repositorio.py` (`ler` e `salvar`) |
