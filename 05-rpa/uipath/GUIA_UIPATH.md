# UiPath - preencher o portal de zeladoria

Papel do UiPath neste projeto: quando o Python roda em `ENVIO_MODO=portal`, ele deixa a fila em `outbox/fila_portal.csv`. O UiPath lê essa fila, preenche o formulário do portal e devolve o protocolo em `outbox/protocolos_portal.csv`.

> Este guia descreve o fluxo para você montar no UiPath Studio. O arquivo `.xaml` não está no repositório porque precisa ser criado e testado no seu Studio. Depois de montado, exporte o projeto para a pasta `uipath/` (é o que o enunciado pede).

## 1. Subir o portal de mentira

```bash
python -m http.server 8080 --directory portal_mock
```

Abra `http://localhost:8080`. Os campos têm `id` fixo, bons para seletores:
`id_ocorrencia`, `poste_id`, `latitude`, `longitude`, `prioridade`, `descricao`, botão `btn_enviar`, resultado `protocolo_gerado`.

## 2. Projeto no Studio

Crie um processo **Main.xaml** (fluxo simples; REFramework é opcional).

**Variáveis:** `dtFila` (DataTable), `row` (DataRow), `dtProtocolos` (DataTable), `protocolo` (String), `tentativas` (Int32).

**Passos:**

1. **Read CSV** `outbox/fila_portal.csv` para `dtFila` (delimitador vírgula, UTF-8).
2. **Build Data Table** `dtProtocolos` com colunas `id` e `protocolo`.
3. **Use Browser / Open Browser** em `http://localhost:8080`.
4. **For Each Row** em `dtFila` (aqui entra o loop obrigatório):
   - **Try Catch** em volta do item (exceções):
     - **Type Into** `id_ocorrencia` ← `row("id")`
     - **Type Into** `poste_id`, `latitude`, `longitude`, `descricao`
     - **Select Item** `prioridade` ← `row("prioridade")` (`NORMAL` ou `URGENTE`)
     - **If** `row("prioridade") = "URGENTE"` → **Log Message** "Chamado urgente"; senão "Chamado normal" (a decisão obrigatória)
     - **Click** `btn_enviar`
     - **Get Text** `protocolo_gerado` → `protocolo`
     - **Add Data Row** em `dtProtocolos`: `{row("id"), protocolo}`
     - **Log Message** `"OK " + row("id") + " -> " + protocolo`
   - **Catch**: **Log Message** nível Error com `exception.Message`, e **Take Screenshot** salvando em `assets/`. O item é pulado e o loop continua.
5. **Write CSV** `dtProtocolos` em `outbox/protocolos_portal.csv`.
6. Fechar o navegador.

## 3. Fechar o ciclo

Depois que o UiPath gravar os protocolos:

```bash
python -m src.main --sincronizar-protocolos
```

Isso troca `FILA_PORTAL` por `PROTOCOLADO` na tabela e grava o número do protocolo. É esse dado que o dashboard do MVP mostra.

## 4. O que printar para o relatório

- Fluxo no Studio (visão geral e o For Each aberto).
- Execução com sucesso (Output panel).
- Execução com falha tratada (por exemplo, desligue o portal e rode: o Catch deve registrar o erro).
- `protocolos_portal.csv` e a tabela já com `PROTOCOLADO`.
