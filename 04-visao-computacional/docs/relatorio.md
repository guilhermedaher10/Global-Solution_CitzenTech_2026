# Rascunho do relatório (vira o PDF de até 5 pts)

> Siga exatamente esta ordem, que é a do professor. Trechos em _itálico_ são para preencher depois do treino.
> Limites: resumo com até **250 palavras**, objetivo com até **50 palavras**.

---

## Título
**Ruas Escuras: detecção em tempo real de falhas na iluminação pública com YOLO26 para ligar o cidadão à prefeitura**

## Integrantes
| Nome completo | RM |
|---|---|
| Guilherme Gonçalves Calil Daher | 98611 |
| | |
| | |
| | |
| | |

## Resumo (até 250 palavras)
Ruas com iluminação pública falha aumentam a sensação de insegurança, favorecem assaltos e causam quedas e
acidentes de pedestres, ciclistas e motociclistas. Mesmo assim, a falha costuma demorar a chegar até a prefeitura,
porque depende de alguém reclamar, e a reclamação chega sem evidência nem prioridade. Este trabalho apresenta o
componente de Visão Computacional do projeto Ruas Escuras, que funciona como ponte entre o cidadão e o poder público.
Treinamos de forma customizada um detector de objetos YOLO26 para identificar luminárias acesas e apagadas em fotos e
vídeos noturnos. O dataset foi montado a partir de conjuntos públicos do Roboflow Universe e de imagens com licença
aberta (Openverse e Wikimedia Commons) e frames de vídeos noturnos, anotados pela equipe, com deduplicação por hash
perceptual e um conjunto de teste de origem diferente da do treino. Sobre as detecções, regras explicáveis
classificam o trecho como iluminado, parcial ou escuro, validam se a foto enviada serve de evidência e calculam a
prioridade do chamado, sempre com os motivos. A solução roda em tempo real com rastreamento (ByteTrack) e painel em
realidade aumentada, e é exposta por uma API REST consumida pelo robô, pela automação e pelo pipeline de dados. Por
padrão, rostos são borrados, metadados são descartados e nenhuma imagem é armazenada. _O modelo final obteve mAP50
de X no conjunto de teste, rodando a Y FPS._ Os resultados indicam que a visão computacional pode transformar uma
reclamação subjetiva em um chamado confirmado, localizado e priorizado.

## Introdução
- O problema e quem sofre: pedestres, ciclistas, motociclistas e moradores que circulam à noite. _Trazer 1 ou 2
  dados reais: nº de reclamações de iluminação no SP156/dados abertos e relação entre iluminação, crime e acidentes
  (citar fonte)._
- Como funciona hoje: depende de o cidadão ligar ou abrir chamado. O chamado chega sem foto validada, sem prioridade,
  e muitas vezes duplicado.
- Onde a visão computacional entra: transformar uma imagem em evidência objetiva (quantos postes, quais apagados,
  quão escura está a cena) de forma automática e em escala, pelo celular do cidadão ou pela câmera de um robô.
- ODS 11 (cidades sustentáveis), 3 (saúde: acidentes), 10 (desigualdades: varredura ativa onde há menos
  reclamações) e 9 (infraestrutura).

## Objetivo (até 50 palavras)
Treinar um detector YOLO26 customizado que identifique, em tempo real, luminárias acesas e apagadas em imagens
noturnas e, com regras explicáveis, classifique o trecho, valide a evidência e priorize o chamado para a prefeitura,
preservando a privacidade do cidadão.

## Explicação técnica das ferramentas
| Ferramenta | Papel |
|---|---|
| **YOLO26 (Ultralytics)** | Detector de uma etapa, sem NMS, otimizado para borda/CPU. Usamos as variantes `n` e `s` pré-treinadas no COCO (transfer learning) |
| **PyTorch + CUDA** | Treino na GPU (RTX 4060 Ti, 8 GB) |
| **Roboflow** | Anotação, versionamento e export do dataset em formato YOLO |
| **Openverse / Wikimedia Commons** | APIs oficiais de imagens com licença aberta (autor e licença registrados) |
| **OpenCV** | Leitura de vídeo, brilho da cena (canal V do HSV), nitidez (variância do Laplaciano), borramento de rostos (Haar/YuNet), painel de RA |
| **ByteTrack** | Rastreamento: o mesmo poste mantém um id entre frames e é contado uma vez no trajeto |
| **ImageHash (pHash)** | Remove imagens repetidas e evita vazamento entre treino e teste |
| **FastAPI + Pydantic** | API REST com contrato tipado (`/v1/analisar`) e documentação automática |
| **Docker** | Empacota a API para o deploy (componente de DevOps) |
| **pytest** | Testes automatizados das regras, do pipeline e da API |

_Incluir o diagrama: foto/vídeo → YOLO26 → regras (trecho, validação, prioridade) → anonimização → JSON → MVP._

## Metodologia (passo a passo)
1. **Definição das classes:** `poste_aceso` e `poste_apagado`, com guia de anotação (`docs/dataset.md`).
2. **Coleta:** _N_ datasets do Roboflow, _N_ imagens com licença aberta e _N_ frames de vídeo.
3. **Unificação:** tradução dos nomes de classe de cada fonte para as nossas, descarte de imagens com classes fora
   do escopo e conversão de polígonos em caixas (`unificar_dataset.py`).
4. **Deduplicação:** hash perceptual com distância ≤ 6 (`deduplicar.py`).
5. **Pré-anotação e revisão:** um modelo-base sugere as caixas e a equipe revisa todas no Roboflow.
6. **Divisão:** treino/validação por fonte; **teste com imagens de origem diferente** (`--teste-fonte`).
7. **Treino:** YOLO26n e YOLO26s, 640 px, até 100 épocas, early stopping (paciência 25), augmentation de
   brilho/exposição para simular câmeras diferentes, sem flip vertical.
8. **Avaliação:** mAP50, mAP50-95, precisão, recall por classe e FPS no conjunto de teste (`avaliar.py`).
9. **Regras de negócio:** limiares em `configs/regras.yaml`, ajustados com exemplos reais.
10. **Tempo real e integração:** `tempo_real.py` (rastreamento + RA) e API consumida pelos outros componentes.

## Exemplos de resultados
_Preencher com:_
- `results/dataset.md` (tamanho do dataset por fonte e classe)
- `results/metricas.md` (tabela YOLO26n × YOLO26s)
- `results/yolo26n/results.png` (curvas de treino) e `confusion_matrix_normalized.png`
- 4 a 6 imagens de `results/exemplos/`: acertos (rua escura → chamado ALTA), recusa de foto diurna e **pelo menos
  2 erros comentados** (o que o modelo errou e por quê)
- Print do JSON da API e do `/docs`

## Conclusão
_Retomar o objetivo, dizer o que funcionou (números), as limitações (poste apagado pouco visível à noite, viés de
imagens estrangeiras) e os próximos passos: mais imagens brasileiras, rodar no robô (ONNX), detectar luminária
encoberta por árvore (encaminhar para poda), mapa de calor de trechos escuros com o Big Data._

**Links:** repositório: https://github.com/guilhermedaher10/Global-Solution_CitzenTech_2026/tree/main/04-visao-computacional
· vídeo: _link do YouTube_
