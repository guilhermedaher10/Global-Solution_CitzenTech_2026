# Roteiro do vídeo (até 5 pts): 3 a 4 minutos

Grave a tela com OBS (gratuito), em 1080p. Narração curta, mostrando mais do que falando. YouTube como **não listado**
e teste o link numa aba anônima.

| Tempo | Cena | Na tela | Fala (resumo) |
|---|---|---|---|
| 0:00 | Problema | Imagem de rua escura + 1 dado real | "Rua escura dá medo, causa acidente e a prefeitura só sabe quando alguém reclama." |
| 0:20 | Solução | Diagrama do fluxo (README) | "Nossa visão computacional transforma uma foto ou um vídeo em chamado confirmado." |
| 0:40 | Dados | Pasta do Roboflow, `results/dataset.md` | "Juntamos N imagens de M fontes, anotamos e testamos com imagens de outra origem." |
| 1:10 | Treino | `results.png`, matriz de confusão, tabela n × s | "YOLO26 com transfer learning: mAP50 de X; o n roda a Y FPS." |
| 1:40 | **Tempo real** | `tempo_real.py` num vídeo noturno: caixas, ids, painel mudando para ESCURA | "Cada poste ganha um id e é contado uma vez. Quando um apagado é confirmado, o chamado é gerado." |
| 2:30 | API | `/docs` → envia foto → JSON com `abrir_chamado` e prioridade | "É assim que o app, o robô e a automação usam o modelo." |
| 2:55 | Validação | Foto de dia → recusada com motivo | "Foto de dia não vira chamado. O cidadão recebe o motivo." |
| 3:10 | Privacidade | Rosto borrado no vídeo | "Rostos borrados, sem metadados, nada armazenado." |
| 3:25 | Fechamento | Arquitetura do produto | "A visão é a ponte: evidência para a prefeitura, resposta para o cidadão." |

**Checklist antes de gravar**
- [ ] `models/best.pt` final no lugar
- [ ] Vídeo noturno de teste com pelo menos 2 postes apagados (frame que o modelo acerta)
- [ ] API rodando (`uvicorn api.main:app`) e uma foto boa e uma diurna à mão
- [ ] `--salvar results/demo.mp4` gravado como backup
