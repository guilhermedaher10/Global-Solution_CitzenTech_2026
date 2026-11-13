`best.pt`: modelo em produção, **YOLO26s** treinado por nós (640 px, 2 classes: `poste_aceso`, `poste_apagado`),
~20 MB. Dados: datasets públicos curados + 135 fotos revisadas pela equipe no Roboflow (versão 1) + 75 imagens
sintéticas de poste apagado (só no treino). Resultado no **teste com fotos reais** (nunca vistas no treino):

| Modelo | mAP50 geral | aceso | **apagado** | precisão | recall | CPU |
|---|---|---|---|---|---|---|
| modelo-base (anterior) | 0,42 | 0,80 | 0,04 | 0,64 | 0,40 | 36 ms |
| YOLO26n | 0,46 | 0,84 | 0,09 | 0,78 | 0,43 | 31 ms |
| **YOLO26s (este)** | **0,50** | **0,84** | **0,16** | **0,84** | **0,47** | 61 ms |
| YOLO26s 960 px | 0,50 | 0,87 | 0,14 | 0,59 | 0,50 | 107 ms |

Em 25 fotos noturnas inéditas do integrante: 1 → 12 postes apagados encontrados. O apagado segue sendo a classe
difícil; a análise de cena (`visao/cena.py`) cobre os casos em que nenhum poste aparece (breu, apagão).

`best.pt`: modelo treinado (copiado automaticamente por `scripts/treinar.py`). Versionado no Git (~5 MB no YOLO26n) para a API rodar logo após o clone.

`face_detection_yunet_2023mar.onnx`: detector de rostos YuNet ([opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), licença MIT, 230 KB),
usado para borrar rostos (LGPD). Sem ele, a API cai no Haar do OpenCV, que confunde reflexo de luz com rosto em
foto noturna (numa foto sem ninguém, o Haar achou 5 "rostos"; o YuNet, 0).
SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
