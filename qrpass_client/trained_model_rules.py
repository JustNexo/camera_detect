"""
Логика из old/main.py: своя модель YOLO + check_access_rule по Rules в users.db.
"""
from __future__ import annotations

import os
import sqlite3
import cv2
import numpy as np
from ultralytics import YOLO


def _db_path() -> str:
    return os.getenv("SQLITE_DB_PATH", "users.db")


def _policy_color_ids() -> tuple[int, ...]:
    raw = (os.getenv("POLICY_COLOR_IDS") or "2,6,7").replace(" ", "")
    if not raw:
        return (2, 6, 7)
    return tuple(int(x) for x in raw.split(",") if x)


def policy_class_person() -> str:
    return (os.getenv("POLICY_CLASS_PERSON") or "Person").strip()


def policy_class_uniform() -> str:
    return (os.getenv("POLICY_CLASS_UNIFORM") or "Red uniform").strip()


def _policy_tracked_casefolds() -> frozenset[str]:
    """
    Учитываем только классы из обученной задачи (как в data.yaml).
    Остальные детекты (случайно с yolov8n.pt/COCO: umbrella, giraffe…) игнорируем.
    """
    raw = (os.getenv("POLICY_TRACKED_CLASSES") or "").strip()
    if raw:
        return frozenset(x.strip().casefold() for x in raw.split(",") if x.strip())
    barrel = (os.getenv("POLICY_CLASS_BARREL") or "Barrel").strip()
    return frozenset(
        {
            policy_class_person().casefold(),
            policy_class_uniform().casefold(),
            barrel.casefold(),
        }
    )


def check_access_rule(camera_id: int, detected_class_name: str) -> bool:
    """True — доступ разрешён, False — нарушение."""
    conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    policy_ids = _policy_color_ids()
    placeholders = ",".join("?" * len(policy_ids))

    is_red_forbidden = False
    is_red_allowed = False

    try:
        cursor.execute(
            f"""
            SELECT 1 FROM Rules
            WHERE camera_id = ? AND color_id IN ({placeholders}) AND access_granted = 0
            LIMIT 1
            """,
            (camera_id, *policy_ids),
        )
        if cursor.fetchone():
            is_red_forbidden = True

        if not is_red_forbidden:
            cursor.execute(
                f"""
                SELECT 1 FROM Rules
                WHERE camera_id = ? AND color_id IN ({placeholders}) AND access_granted = 1
                LIMIT 1
                """,
                (camera_id, *policy_ids),
            )
            if cursor.fetchone():
                is_red_allowed = True
    except sqlite3.Error as exc:
        print(f"БД check_access_rule: {exc}")
        is_red_forbidden = True
    finally:
        conn.close()

    is_no_red_zone = is_red_forbidden or (not is_red_forbidden and not is_red_allowed)

    person = policy_class_person()
    uniform = policy_class_uniform()
    cn = (detected_class_name or "").strip()
    # COCO: "person", обучение Roboflow: "Person" — сравниваем без учёта регистра
    cnf = cn.casefold()
    if is_no_red_zone:
        return cnf == person.casefold()
    return cnf == uniform.casefold()


def draw_label(
    frame: np.ndarray,
    text: str,
    pos: tuple[int, int],
    color: tuple[int, int, int] = (255, 255, 255),
    bg_color: tuple[int, int, int] = (0, 0, 255),
) -> None:
    font_face = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.8
    thickness = 2
    (text_w, text_h), baseline = cv2.getTextSize(text, font_face, scale, thickness)
    x, y = pos
    cv2.rectangle(frame, (x, y - text_h - baseline), (x + text_w, y + baseline), bg_color, -1)
    cv2.putText(frame, text, (x, y), font_face, scale, color, thickness, cv2.LINE_AA)


def annotate_trained_violations(
    frame: np.ndarray,
    camera_id: int,
    model: YOLO,
    conf_threshold: float,
) -> tuple[np.ndarray, bool, str]:
    """Один проход модели; разметка как в old/main.py при нарушении."""
    class_names: dict[int, str] = model.names if isinstance(model.names, dict) else dict(model.names)

    results = model(frame, verbose=False)
    r0 = results[0]
    out = r0.plot()

    boxes = r0.boxes
    if boxes is None or len(boxes) == 0:
        return out, False, ""

    violation = False
    parts: list[str] = []
    tracked = _policy_tracked_casefolds()

    for box in boxes:
        conf = float(box.conf[0])
        if conf < conf_threshold:
            continue
        cls_id = int(box.cls[0])
        class_name = class_names.get(cls_id, f"id_{cls_id}")
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        if class_name.strip().casefold() not in tracked:
            continue

        if not check_access_rule(camera_id, class_name):
            violation = True
            parts.append(class_name)
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 3)
            draw_label(out, f"{class_name}: FORBIDDEN", (x1, y1 - 5))

    text = ""
    if violation and parts:
        text = "Нарушение: " + ", ".join(sorted(set(parts)))
    return out, violation, text
