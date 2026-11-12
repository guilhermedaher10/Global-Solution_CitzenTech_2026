# Dataset: de onde vêm as imagens e como montamos

## Classes
| id | Classe | O que marcar |
|---|---|---|
| 0 | `poste_aceso` | A luminária acesa (o ponto de luz e a cabeça do poste). Marque a **luminária**, não o poste inteiro |
| 1 | `poste_apagado` | A luminária apagada num contexto em que deveria estar acesa (noite, entardecer) |

**Guia de anotação (vale para todos que ajudarem):**
- **Padrão único:** antes de anotar, veja como o maior dataset do Roboflow desenha as caixas (só luminária ou poste inteiro) e siga o mesmo. Misturar padrões derruba o mAP.
- Caixa justa na luminária, incluindo o halo só se estiver muito forte.
- Luminária apagada **de dia** também pode ser `poste_apagado`: o aspecto visual é o mesmo (lâmpada sem luz). Quem recusa foto diurna como evidência é a regra de validação, não o modelo.
- Luminária encoberta por árvore, mas acesa: `poste_aceso`.
- Na dúvida, não marque. Uma caixa errada atrapalha mais que uma caixa faltando.

## Fontes
Preencha a tabela depois de rodar os scripts (a contagem sai em `results/dataset.md`).

| Fonte | Tipo | Licença | Imagens usadas | Link |
|---|---|---|---|---|
| street-light-off (datasets-cobjh) | Roboflow, anotado | _conferir_ | | https://universe.roboflow.com/datasets-cobjh/street-light-off |
| street-light-lbrt8 (carsmoke-detection) | Roboflow, anotado | _conferir_ | | https://universe.roboflow.com/carsmoke-detection/street-light-lbrt8 |
| led-only (streetlight-detection) | Roboflow, anotado | _conferir_ | | https://universe.roboflow.com/streetlight-detection/led-only |
| poles-dataset-e00t2 (sba-pothole) | Roboflow, anotado | CC BY 4.0 | | https://universe.roboflow.com/sba-pothole/poles-dataset-e00t2 |
| streetlight-night (sashank-s) | Roboflow, anotado | CC BY 4.0 | | https://universe.roboflow.com/sashank-s/streetlight-night |
| Openverse (Flickr etc.) | web, anotado por nós | CC (por imagem, no manifesto) | | https://openverse.org |
| Wikimedia Commons | web, anotado por nós | CC/domínio público (por imagem) | | https://commons.wikimedia.org |
| Frames de vídeos noturnos | vídeo, anotado por nós | uso acadêmico; só o modelo é publicado | | ver `data/bruto/frames/manifesto.csv` |

Extra para o relatório: o artigo *Comprehensive Dataset for Urban Streetlight Analysis* (arXiv 2407.01117)
traz ~800 fotos rotuladas como funcionando / com defeito / apagado. Pode servir de teste externo.

## Passo a passo

```bash
# 0. ambiente
pip install -r requirements-dados.txt
cp .env.example .env                       # cole a ROBOFLOW_API_KEY

# 1. datasets prontos (já anotados)
python scripts/baixar_roboflow.py
python scripts/unificar_dataset.py --listar   # confira os nomes de classe -> configs/classes.yaml

# 2. modelo-base só com o Roboflow (serve para pré-anotar o resto)
python scripts/unificar_dataset.py
python scripts/treinar.py --epocas 60 --nome base

# 3. imagens da web e de vídeo
python scripts/coletar_web.py --max 120
python scripts/extrair_frames.py --fonte "https://www.youtube.com/watch?v=..." --a-cada 2 --max 200
python scripts/deduplicar.py               # tira as repetidas e as que já estão no Roboflow
python scripts/pre_anotar.py               # o modelo-base sugere as caixas

# 4. no Roboflow: suba data/anotar_yolo/, revise TODAS as caixas, gere uma versão e exporte
#    em formato "YOLOv8" para data/anotado/

# 5. dataset final e treino de verdade
python scripts/unificar_dataset.py --teste-fonte anotado   # teste = nossas imagens (generalização honesta)
python scripts/treinar.py --modelo yolo26n.pt --nome yolo26n
python scripts/treinar.py --modelo yolo26s.pt --nome yolo26s --nao-copiar
python scripts/avaliar.py --modelo runs/yolo26n/weights/best.pt --modelo runs/yolo26s/weights/best.pt
```

## Por que esse desenho
- **Treino customizado de verdade:** curadoria de várias fontes, tradução de classes, anotação própria e
  fine-tuning do YOLO26 pré-treinado no COCO (transfer learning).
- **Teste honesto:** com `--teste-fonte anotado`, o modelo é avaliado em imagens de origem diferente das do treino.
  Isso evita a métrica inflada de testar com fotos "irmãs" das de treino.
- **Sem vazamento:** o `deduplicar.py` usa hash perceptual e remove imagens da web que já estão no Roboflow.
