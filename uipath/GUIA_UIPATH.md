# UiPath - registrar o chamado no portal de zeladoria

Papel do UiPath neste projeto: quando o Python roda em `ENVIO_MODO=portal`, ele deixa a fila em `outbox/fila_portal.csv`. O UiPath lê essa fila, preenche o formulário do portal e devolve o protocolo em `outbox/protocolos_portal.csv`. Isso cobre o "registra no sistema da prefeitura (portal simulado ou SP156)" do `docs/arquitetura.md`.

> Este guia descreve o fluxo para montar no UiPath Studio. O projeto exportado (`Main.xaml` e demais arquivos) vai nesta pasta `uipath/`, ao lado deste guia, porque o enunciado pede o fluxo exportado.

## 1. Subir o portal de mentira

```powershell
python -m http.server 8080 --directory portal_mock
```

Abra `http://localhost:8080`. Os campos têm `id` fixo, bons para seletores:
`id_captura`, `tipos_chamado`, `latitude`, `longitude`, `prioridade` (alta, media ou baixa), `descricao`, botão `btn_enviar` e resultado `protocolo_gerado`.

## 2. O que o Python entrega

`outbox/fila_portal.csv`, **um chamado por trecho** (os duplicados por proximidade já foram agrupados no principal), ordenado da maior para a menor prioridade:

| Coluna | Conteúdo |
|---|---|
| `id_captura` | identificador do chamado (vem da Visão) |
| `latitude`, `longitude` | local do problema |
| `tipos_chamado` | `conserto_poste`, `buraco`, ... (separados por `\|`) |
| `prioridade` | `alta`, `media` ou `baixa` (calculada pela Visão) |
| `descricao` | resumo do trecho e dos motivos da validação |
| `pdf` | caminho do PDF do chamado |
| `agrupados` | quantos chamados próximos foram consolidados neste |

## 3. Projeto no Studio

Crie um processo **Main.xaml** (fluxo simples; REFramework é opcional).

**Variáveis:** `dtFila` (DataTable), `row` (DataRow), `dtProtocolos` (DataTable), `protocolo` (String).

**Passos:**

1. **Read CSV** `outbox/fila_portal.csv` para `dtFila` (delimitador vírgula, UTF-8).
2. **Build Data Table** `dtProtocolos` com colunas `id_captura` e `protocolo`.
3. **Use Browser / Open Browser** em `http://localhost:8080`.
4. **For Each Row** em `dtFila` (o loop):
   - **Try Catch** em volta do item (exceções):
     - **Type Into** `id_captura` ← `row("id_captura")`
     - **Type Into** `tipos_chamado`, `latitude`, `longitude`, `descricao`
     - **Select Item** `prioridade` ← `row("prioridade")`
     - **If** `row("prioridade").ToString = "alta"` → **Log Message** "Chamado de prioridade alta"; senão "Chamado de prioridade normal/baixa" (a decisão)
     - **Click** `btn_enviar`
     - **Get Text** `protocolo_gerado` → `protocolo`
     - **Add Data Row** em `dtProtocolos`: `{row("id_captura"), protocolo}`
     - **Log Message** `"OK " + row("id_captura") + " -> " + protocolo`
   - **Catch**: **Log Message** nível Error com `exception.Message`, e **Take Screenshot** salvando em `assets/`. O item é pulado e o loop continua.
5. **Write CSV** `dtProtocolos` em `outbox/protocolos_portal.csv` (com cabeçalho; as colunas precisam se chamar exatamente `id_captura` e `protocolo`).
6. Fechar o navegador.

## 4. Fechar o ciclo

Depois que o UiPath gravar os protocolos:

```powershell
python -m src.main --sincronizar-protocolos
```

Isso faz três coisas na tabela de chamados:
- o chamado principal passa de `confirmado` para **`encaminhado`** e recebe o número do protocolo;
- os chamados agrupados nele (mesmo trecho) passam para `encaminhado` com o **mesmo protocolo**;
- a coluna interna `rpa_etapa` vira `protocolado`.

É essa mudança de status que o app do cidadão mostra.

## 5. O que printar para o relatório

- Fluxo no Studio (visão geral e o For Each aberto).
- Execução com sucesso (Output panel).
- Execução com falha tratada (desligue o portal e rode: o Catch deve registrar o erro).
- `protocolos_portal.csv` e a tabela já com `encaminhado` e o protocolo.
