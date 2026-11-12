# Plano: Visão Computacional, de 09/11 a 19/11

| Dia | Data | Tarefa | Pronto quando |
|---|---|---|---|
| 1 | seg 09/11 | Repo, código base, testes, contrato da API ✅ | Grupo com o link e o `docs/integracao.md` |
| 2 | ter 10/11 | Conta no Roboflow, `.env`, `baixar_roboflow.py`, `unificar_dataset.py --listar`, ajustar aliases. **Treino-base** (60 épocas) | `runs/base` com mAP anotado |
| 3 | qua 11/11 | `coletar_web.py` + `extrair_frames.py` (2 ou 3 vídeos noturnos) + `deduplicar.py` + `pre_anotar.py` | `data/anotar_yolo/` pronto |
| 4 | qui 12/11 | Revisar as caixas no Roboflow (meta: 300+ imagens nossas, 300+ `poste_apagado` no total). Exportar para `data/anotado/` | Versão do dataset gerada |
| 5 | sex 13/11 | `unificar_dataset.py --teste-fonte anotado`, treinar YOLO26n e YOLO26s, `avaliar.py` | `results/metricas.md` e `models/best.pt` |
| 6 | sáb 14/11 | Analisar erros (`analisar_pasta.py`), mais imagens da classe que erra, ajustar `regras.yaml`, retreinar se valer a pena | Erros comentados para o relatório |
| 7 | dom 15/11 | Integração: API no Docker, passar a URL ao time (DevOps, robô, RPA). Gravar `tempo_real.py --salvar` | Alguém do time consumindo a API |
| 8 | seg 16/11 | **Vídeo** (`docs/roteiro-video.md`) | YouTube como não listado |
| 9 | ter 17/11 | **PDF** a partir de `docs/relatorio.md` | PDF revisado |
| 10 | qua 18/11 | Folga: README, links em aba anônima, nomes e RMs | Tudo conferido |
| — | qui 19/11 | **Entregar até 23h55** no Teams da disciplina | ✅ |

## Riscos
| Risco | Plano B |
|---|---|
| Poucos `poste_apagado` | Priorizar no Roboflow os datasets "off"; buscar mais com termos "streetlight off", "broken street light"; frames de vídeos de bairros com falha |
| Datasets do Roboflow com padrões de caixa diferentes | Ficar só com os de padrão igual ao maior; documentar |
| mAP baixo em `poste_apagado` | Normal (é o caso difícil): mostrar que a regra do trecho + sensor do robô compensam; comentar no relatório |
| Time atrasar a integração | A API funciona sozinha: demo com o `/docs` e o `tempo_real.py --eventos` |
