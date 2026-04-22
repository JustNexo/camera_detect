"""
Логика нарушений по цвету одежды и правилам из users.db — как в старом main.py.
Требуется модель сегментации Ultralytics (yolov8n-seg.pt) и таблицы Colors, Rules, Cameras.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO


def _db_path() -> str:
    return os.getenv("SQLITE_DB_PATH", "users.db")


def get_access_rules(camera_id: int) -> tuple[set[str], set[str]]:
    conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.access_granted, c.name
        FROM Rules r
        JOIN Colors c ON r.color_id = c.id
        WHERE r.camera_id = ?
        """,
        (camera_id,),
    )
    rules = cursor.fetchall()
    conn.close()

    allowed_colors: set[str] = set()
    forbidden_colors: set[str] = set()
    for access_granted, color_name in rules:
        if access_granted:
            allowed_colors.add(color_name)
        else:
            forbidden_colors.add(color_name)
    return allowed_colors, forbidden_colors


def get_access_rule(camera_id: int, color_name: str) -> bool:
    """True = доступ разрешён, False = нарушение (как в старом коде)."""
    allowed_colors, forbidden_colors = get_access_rules(camera_id)

    if color_name == "Запрещенный цвет":
        if "ярко-красный" in forbidden_colors:
            return True
        if "ярко-красный" in allowed_colors:
            return False
    else:
        if color_name in allowed_colors:
            return True
        if color_name in forbidden_colors:
            return False

    return True


def get_color_namee(frame: np.ndarray, person_segments: list) -> str:
    conn = sqlite3.connect(_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT name, lower_bound, upper_bound FROM Colors")
    color_data = cursor.fetchall()
    conn.close()

    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    contour_mask = np.zeros(frame.shape[:2], dtype=np.uint8)

    for segment in person_segments:
        segment = np.array(segment, dtype=np.int32)
        cv2.drawContours(contour_mask, [segment], -1, 255, thickness=cv2.FILLED)

    masked_frame = cv2.bitwise_and(hsv_frame, hsv_frame, mask=contour_mask)

    total_pixels = cv2.countNonZero(contour_mask)
    if total_pixels == 0:
        return "Контур не найден"

    for name, lower_bound, upper_bound in color_data:
        lower = np.array(eval(lower_bound), dtype=np.uint8)
        upper = np.array(eval(upper_bound), dtype=np.uint8)
        mask = cv2.inRange(masked_frame, lower, upper)
        mask_pixels = cv2.countNonZero(mask)
        ratio = mask_pixels / total_pixels

        if ratio > 0.15:
            return name

    return "Запрещенный цвет"


def detect_persons_seg(
    model: YOLO, frame: np.ndarray, conf_threshold: float
) -> tuple[list[tuple[Any, Any]], Any]:
    """Список (box, segments) для класса person (0), как в старом detect_person."""
    results = model(frame, verbose=False)
    if not results or not results[0].boxes:
        return [], results

    det = results[0].boxes
    masks = results[0].masks
    if masks is None:
        return [], results

    persons: list[tuple[Any, Any]] = []
    for i in range(len(det)):
        box = det.xyxy[i]
        conf = det.conf[i]
        cls = det.cls[i]
        if int(cls) == 0 and float(conf) >= conf_threshold:
            person_segments = masks[i].xy
            persons.append((box, person_segments))
    return persons, results


def draw_label(frame: np.ndarray, text: str, pos: tuple[int, int], color: tuple[int, int, int]) -> None:
    font_face = cv2.FONT_HERSHEY_COMPLEX
    scale = 0.9
    thickness = 2
    text_size = cv2.getTextSize(text, font_face, scale, thickness)
    x, y = pos
    text_w, text_h = text_size[0]
    cv2.rectangle(frame, (x, y - text_h - 10), (x + text_w, y + 5), (0, 0, 0), -1)
    cv2.putText(frame, text, (x, y), font_face, scale, color, thickness)


def annotate_color_violations(
    frame: np.ndarray,
    camera_id: int,
    model: YOLO,
    conf_threshold: float,
) -> tuple[np.ndarray, bool, str]:
    """
    Возвращает кадр с разметкой, флаг нарушения и текст для API.
    """
    persons, results = detect_persons_seg(model, frame, conf_threshold)
    violation = False
    violation_type = ""

    r0 = results[0]
    if r0.masks is not None:
        base = r0.plot()
    else:
        base = frame.copy()

    out = base
    for box, person_segments in persons:
        x1, y1, x2, y2 = map(int, box)
        person_mask = [person_segments]
        color_name = get_color_namee(frame, person_mask)

        if not get_access_rule(camera_id, color_name):
            violation = True
            violation_type = f"Запрещённый цвет одежды ({color_name})"
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
            draw_label(out, "запрещенный цвет", (x1, y1 - 10), (0, 255, 0))

    return out, violation, violation_type
