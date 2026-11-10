"""Treina o YOLO26 no dataset unificado (transfer learning a partir do COCO).

    python scripts/treinar.py                                  # yolo26n, 100 épocas
    python scripts/treinar.py --modelo yolo26s.pt --epocas 150 --nome yolo26s
    python scripts/treinar.py --exportar onnx                  # também gera .onnx (robô/Raspberry)

Ao final copia o melhor peso para models/best.pt e as curvas para results/<nome>/.
"""
from __future__ import annotations

import argparse
import shutil
import sys

from _comum import DATA, RAIZ


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dados", default=str(DATA / "final" / "data.yaml"))
    ap.add_argument("--modelo", default="yolo26n.pt", help="yolo26n.pt, yolo26s.pt, ...")
    ap.add_argument("--epocas", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=-1, help="-1 = automático pela memória da GPU")
    ap.add_argument("--paciencia", type=int, default=25, help="para se não melhorar em N épocas")
    ap.add_argument("--nome", default=None, help="nome do experimento (padrão: nome do modelo)")
    ap.add_argument("--device", default=None, help="0 = primeira GPU, cpu = processador")
    ap.add_argument("--exportar", choices=["onnx", "openvino", "tflite"], default=None)
    ap.add_argument("--nao-copiar", action="store_true", help="não sobrescrever models/best.pt")
    args = ap.parse_args()

    from ultralytics import YOLO

    nome = args.nome or args.modelo.replace(".pt", "")
    model = YOLO(args.modelo)
    model.train(
        data=args.dados, epochs=args.epocas, imgsz=args.imgsz, batch=args.batch,
        patience=args.paciencia, device=args.device, project=str(RAIZ / "runs"), name=nome,
        exist_ok=True, seed=42, deterministic=True, plots=True,
        # Augmentation pensada para foto noturna: variar brilho/exposição ajuda a generalizar
        # entre câmera de celular, dashcam e câmera do robô. Sem flip vertical (poste não fica de ponta-cabeça).
        hsv_h=0.015, hsv_s=0.6, hsv_v=0.5, degrees=3.0, translate=0.1, scale=0.5,
        fliplr=0.5, flipud=0.0, mosaic=1.0, close_mosaic=10,
    )

    pasta = RAIZ / "runs" / nome
    best = pasta / "weights" / "best.pt"
    destino_res = RAIZ / "results" / nome
    destino_res.mkdir(parents=True, exist_ok=True)
    for arq in ("results.png", "results.csv", "confusion_matrix.png", "confusion_matrix_normalized.png",
                "BoxPR_curve.png", "BoxF1_curve.png", "PR_curve.png", "F1_curve.png",
                "labels.jpg", "val_batch0_pred.jpg", "val_batch0_labels.jpg", "args.yaml"):
        if (pasta / arq).exists():
            shutil.copy2(pasta / arq, destino_res / arq)

    if not args.nao_copiar and best.exists():
        (RAIZ / "models").mkdir(exist_ok=True)
        shutil.copy2(best, RAIZ / "models" / "best.pt")
        print(f"\nmodels/best.pt atualizado a partir de {best}")
    if args.exportar and best.exists():
        caminho = YOLO(str(best)).export(format=args.exportar, imgsz=args.imgsz)
        print(f"exportado: {caminho}")
    print(f"Curvas e matriz de confusão em {destino_res}. Próximo passo: python scripts/avaliar.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
