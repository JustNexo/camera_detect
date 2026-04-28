from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Обучение/дообучение YOLOv8s на вашем датасете."
    )
    p.add_argument(
        "--data",
        required=True,
        help="Путь к data.yaml (YOLO dataset config).",
    )
    p.add_argument(
        "--model",
        default="yolov8s.pt",
        help="Базовая модель: yolov8s.pt или путь к вашему checkpoint .pt",
    )
    p.add_argument("--epochs", type=int, default=50, help="Число эпох")
    p.add_argument("--imgsz", type=int, default=640, help="Размер входа")
    p.add_argument("--batch", type=int, default=8, help="Размер batch")
    p.add_argument(
        "--device",
        default="0",
        help='GPU индекс ("0") или "cpu"',
    )
    p.add_argument("--workers", type=int, default=4, help="Число dataloader workers")
    p.add_argument("--lr0", type=float, default=0.001, help="Начальный learning rate")
    p.add_argument("--patience", type=int, default=15, help="Early stopping patience")
    p.add_argument("--project", default="runs/train", help="Папка проекта для логов")
    p.add_argument("--name", default="yolov8s_custom", help="Имя эксперимента")
    p.add_argument(
        "--resume",
        action="store_true",
        help="Продолжить прерванное обучение (resume=True).",
    )
    p.add_argument(
        "--close-mosaic",
        type=int,
        default=10,
        help="За сколько эпох до конца выключить mosaic.",
    )
    p.add_argument(
        "--cache",
        default=False,
        action="store_true",
        help="Кэшировать датасет в RAM (быстрее, но больше памяти).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_path = Path(args.data).expanduser().resolve()
    if not data_path.is_file():
        raise FileNotFoundError(f"data.yaml не найден: {data_path}")

    model_ref = str(Path(args.model).expanduser().resolve()) if args.model.endswith(".pt") and Path(args.model).exists() else args.model
    model = YOLO(model_ref)

    print("=== YOLOv8s train start ===")
    print(f"data: {data_path}")
    print(f"model: {model_ref}")
    print(f"epochs: {args.epochs}, imgsz: {args.imgsz}, batch: {args.batch}, device: {args.device}")

    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        lr0=args.lr0,
        patience=args.patience,
        project=args.project,
        name=args.name,
        resume=args.resume,
        close_mosaic=args.close_mosaic,
        cache=args.cache,
        pretrained=True,
        verbose=True,
    )

    print("=== Training finished ===")
    print("Best weights: <project>/<name>/weights/best.pt")


if __name__ == "__main__":
    main()

