# models/

`best.pt`: modelo treinado (copiado automaticamente por `scripts/treinar.py`). Versionado no Git (~5 MB no YOLO26n) para a API rodar logo após o clone.

`face_detection_yunet_2023mar.onnx`: detector de rostos YuNet ([opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), licença MIT, 230 KB),
usado para borrar rostos (LGPD). Sem ele, a API cai no Haar do OpenCV, que confunde reflexo de luz com rosto em
foto noturna (numa foto sem ninguém, o Haar achou 5 "rostos"; o YuNet, 0).
SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`
