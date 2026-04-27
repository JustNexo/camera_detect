from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
from ultralytics import YOLO


@dataclass
class TrackState:
    last_cx: float
    last_cy: float
    counted: bool = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Проверка детекта/подсчета трупов животных по видео (YOLO ONNX)."
    )
    p.add_argument("--model", required=True, help="Путь к best.onnx")
    p.add_argument("--video", required=True, help="Путь к входному видео")
    p.add_argument("--out-video", default="pig_count_preview.mp4", help="Путь к выходному видео")
    p.add_argument("--out-csv", default="pig_count_events.csv", help="CSV с событиями пересечения")
    p.add_argument("--out-json", default="pig_count_summary.json", help="JSON с итогом")
    p.add_argument("--conf", type=float, default=0.35, help="Порог confidence")
    p.add_argument(
        "--line-y-ratio",
        type=float,
        default=0.65,
        help="Положение контрольной линии по высоте кадра (0..1)",
    )
    p.add_argument(
        "--direction",
        choices=("down", "up"),
        default="down",
        help="Направление пересечения линии для подсчета",
    )
    p.add_argument(
        "--class-id",
        type=int,
        default=None,
        help="ID класса трупа (если None, считаем все детекты)",
    )
    p.add_argument(
        "--class-name",
        default=None,
        help="Имя класса трупа (например carcass). Используется, если class-id не задан.",
    )
    p.add_argument(
        "--tracker",
        default="bytetrack.yaml",
        help="Трекер Ultralytics (обычно bytetrack.yaml)",
    )
    p.add_argument(
        "--device",
        default="cpu",
        help="Устройство инференса для Ultralytics (для onnx рекомендуем cpu)",
    )
    return p.parse_args()


def should_use_detection(cls_id: int, names: dict[int, str], args: argparse.Namespace) -> bool:
    if args.class_id is not None:
        return cls_id == args.class_id
    if args.class_name:
        return names.get(cls_id, "").lower() == args.class_name.strip().lower()
    return True


def main() -> None:
    args = parse_args()
    if args.device.lower() == "cpu":
        # Защита от попыток притянуть onnxruntime-gpu на окружениях без CUDA DLL.
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    model = YOLO(args.model)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Не удалось открыть видео: {args.video}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    line_y = int(max(0, min(h - 1, args.line_y_ratio * h)))

    out_video = Path(args.out_video)
    out_video.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_video), fourcc, fps, (w, h))

    events: list[dict] = []
    states: dict[int, TrackState] = {}
    total_count = 0
    frame_idx = 0
    t0 = time.perf_counter()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1

        results = model.track(
            source=frame,
            persist=True,
            verbose=False,
            conf=args.conf,
            tracker=args.tracker,
            device=args.device,
        )
        res = results[0]
        names = res.names if isinstance(res.names, dict) else {}

        if res.boxes is not None and res.boxes.id is not None:
            ids = res.boxes.id.int().cpu().tolist()
            xyxy = res.boxes.xyxy.cpu().tolist()
            cls_ids = res.boxes.cls.int().cpu().tolist()
            confs = res.boxes.conf.cpu().tolist()

            for tid, box, cls_id, conf in zip(ids, xyxy, cls_ids, confs):
                if not should_use_detection(cls_id, names, args):
                    continue
                x1, y1, x2, y2 = box
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0

                st = states.get(tid)
                crossed = False
                if st is not None and not st.counted:
                    if args.direction == "down":
                        crossed = st.last_cy < line_y <= cy
                    else:
                        crossed = st.last_cy > line_y >= cy

                if crossed:
                    st.counted = True
                    total_count += 1
                    event = {
                        "track_id": tid,
                        "frame": frame_idx,
                        "seconds": round(frame_idx / fps, 3),
                        "confidence": round(float(conf), 4),
                        "class_id": cls_id,
                        "class_name": names.get(cls_id, str(cls_id)),
                    }
                    events.append(event)

                if st is None:
                    states[tid] = TrackState(last_cx=cx, last_cy=cy, counted=False)
                else:
                    st.last_cx = cx
                    st.last_cy = cy

                color = (0, 200, 0) if states[tid].counted else (0, 170, 255)
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                label = f"id={tid} {names.get(cls_id, cls_id)} {conf:.2f}"
                cv2.putText(
                    frame,
                    label,
                    (int(x1), max(20, int(y1) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                    cv2.LINE_AA,
                )

        cv2.line(frame, (0, line_y), (w - 1, line_y), (255, 80, 80), 2)
        cv2.putText(
            frame,
            f"count={total_count} direction={args.direction}",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        writer.write(frame)

    cap.release()
    writer.release()
    elapsed = max(1e-9, time.perf_counter() - t0)
    proc_fps = frame_idx / elapsed
    video_seconds = frame_idx / fps if fps > 0 else 0.0
    realtime_factor = (video_seconds / elapsed) if elapsed > 0 else 0.0

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(
            f, fieldnames=["track_id", "frame", "seconds", "confidence", "class_id", "class_name"]
        )
        wcsv.writeheader()
        for e in events:
            wcsv.writerow(e)

    summary = {
        "model": str(Path(args.model).resolve()),
        "video": str(Path(args.video).resolve()),
        "line_y_ratio": args.line_y_ratio,
        "direction": args.direction,
        "total_count": total_count,
        "events_count": len(events),
        "frames_processed": frame_idx,
        "video_fps": round(float(fps), 3),
        "video_duration_seconds": round(float(video_seconds), 3),
        "processing_seconds": round(float(elapsed), 3),
        "processing_fps": round(float(proc_fps), 3),
        "realtime_factor": round(float(realtime_factor), 3),
        "events_csv": str(out_csv.resolve()),
        "preview_video": str(out_video.resolve()),
    }
    out_json = Path(args.out_json)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
