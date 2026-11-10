# data/

Nada aqui vai para o Git (imagens de terceiros e arquivos pesados). Estrutura gerada pelos scripts:

```
bruto/roboflow/<projeto>/   datasets do Roboflow (formato YOLO)       baixar_roboflow.py
bruto/web/<termo>/          imagens da busca + manifesto.csv (fonte)  coletar_web.py
bruto/videos/               vídeos baixados                           extrair_frames.py
bruto/frames/<video>/       frames extraídos dos vídeos               extrair_frames.py
anotar/                     imagens únicas para anotar no Roboflow    deduplicar.py
anotado/                    export YOLO do que você anotou            (download do Roboflow)
final/                      dataset unificado usado no treino         unificar_dataset.py
```
