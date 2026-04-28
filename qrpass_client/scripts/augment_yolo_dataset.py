from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Аугментация YOLO-датасета (images/labels) для дообучения."
    )
    p.add_argument("--images", required=True, help="Папка с исходными изображениями")
    p.add_argument("--labels", default="", help="Папка с .txt разметкой YOLO (опционально)")
    p.add_argument("--out-images", required=True, help="Куда сохранить аугментированные изображения")
    p.add_argument("--out-labels", default="", help="Куда сохранить аугментированные labels (опционально)")
    p.add_argument(
        "--copies-per-image",
        type=int,
        default=8,
        help="Сколько аугментированных копий делать на 1 исходное фото",
    )
    p.add_argument(
        "--copy-original",
        action="store_true",
        help="Копировать исходные изображения и labels в output",
    )
    p.add_argument("--seed", type=int, default=42, help="Сид генератора случайных чисел")
    return p.parse_args()


def read_label_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    txt = path.read_text(encoding="utf-8", errors="replace").strip()
    if not txt:
        return []
    return txt.splitlines()


def hflip_label_line(line: str) -> str:
    parts = line.strip().split()
    if len(parts) < 3:
        return line
    cls = parts[0]
    vals = [float(x) for x in parts[1:]]
    for i in range(0, len(vals), 2):
        vals[i] = 1.0 - vals[i]
    return " ".join([cls] + [f"{v:.6f}" for v in vals])


def vflip_label_line(line: str) -> str:
    parts = line.strip().split()
    if len(parts) < 3:
        return line
    cls = parts[0]
    vals = [float(x) for x in parts[1:]]
    for i in range(1, len(vals), 2):
        vals[i] = 1.0 - vals[i]
    return " ".join([cls] + [f"{v:.6f}" for v in vals])


def apply_non_geo_aug(img: np.ndarray) -> np.ndarray:
    out = img.copy()
    # Яркость/контраст
    alpha = random.uniform(0.8, 1.25)
    beta = random.randint(-25, 25)
    out = cv2.convertScaleAbs(out, alpha=alpha, beta=beta)

    # HSV jitter
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.int16)
    hsv[..., 0] = (hsv[..., 0] + random.randint(-10, 10)) % 180
    hsv[..., 1] = np.clip(hsv[..., 1] + random.randint(-30, 30), 0, 255)
    hsv[..., 2] = np.clip(hsv[..., 2] + random.randint(-30, 30), 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # Иногда blur
    if random.random() < 0.35:
        k = random.choice([3, 5])
        out = cv2.GaussianBlur(out, (k, k), 0)

    # Иногда шум
    if random.random() < 0.35:
        noise = np.random.normal(0, random.uniform(5, 14), out.shape).astype(np.float32)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return out


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)

    in_images = Path(args.images).expanduser().resolve()
    in_labels = Path(args.labels).expanduser().resolve() if args.labels else None
    out_images = Path(args.out_images).expanduser().resolve()
    out_labels = Path(args.out_labels).expanduser().resolve() if args.out_labels else None
    out_images.mkdir(parents=True, exist_ok=True)
    if out_labels is not None:
        out_labels.mkdir(parents=True, exist_ok=True)

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    imgs = [p for p in sorted(in_images.iterdir()) if p.suffix.lower() in exts]
    if not imgs:
        raise RuntimeError(f"Нет изображений в {in_images}")

    total_written = 0
    for img_path in imgs:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        stem = img_path.stem
        if in_labels is not None:
            label_path = in_labels / f"{stem}.txt"
            base_lines = read_label_lines(label_path)
        else:
            base_lines = []

        if args.copy_original:
            out_img_path = out_images / img_path.name
            cv2.imwrite(str(out_img_path), img)
            if out_labels is not None:
                (out_labels / f"{stem}.txt").write_text(
                    ("\n".join(base_lines) + "\n") if base_lines else "",
                    encoding="utf-8",
                )
            total_written += 1

        for i in range(args.copies_per_image):
            aug_img = apply_non_geo_aug(img)
            aug_lines = list(base_lines)
            suffix_parts: list[str] = ["aug", f"{i:02d}"]

            if random.random() < 0.5:
                aug_img = cv2.flip(aug_img, 1)
                aug_lines = [hflip_label_line(x) for x in aug_lines]
                suffix_parts.append("hflip")

            if random.random() < 0.15:
                aug_img = cv2.flip(aug_img, 0)
                aug_lines = [vflip_label_line(x) for x in aug_lines]
                suffix_parts.append("vflip")

            out_name = f"{stem}_{'_'.join(suffix_parts)}{img_path.suffix.lower()}"
            out_img_path = out_images / out_name
            cv2.imwrite(str(out_img_path), aug_img)
            if out_labels is not None:
                out_lbl_path = out_labels / f"{Path(out_name).stem}.txt"
                out_lbl_path.write_text(
                    ("\n".join(aug_lines) + "\n") if aug_lines else "",
                    encoding="utf-8",
                )
            total_written += 1

    print(f"Done. Images written: {total_written}")
    print(f"Output images: {out_images}")
    if out_labels is not None:
        print(f"Output labels: {out_labels}")


if __name__ == "__main__":
    main()
