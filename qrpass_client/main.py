import os
import random
import sqlite3
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import requests
from dotenv import load_dotenv
from ultralytics import YOLO

load_dotenv()

# RTSP по TCP (часто стабильнее UDP): в .env RTSP_TRANSPORT_TCP=true
if os.getenv("RTSP_TRANSPORT_TCP", "").strip().lower() in ("1", "true", "yes"):
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("API_TOKEN", "change_me_api_token")
# Если задано (например http://127.0.0.1:8088), отправка идёт через локальный qrpass_edge.
# Детекция и цикл остаются в qrpass_client; edge только транспорт/очередь.
EDGE_BRIDGE_URL = os.getenv("EDGE_BRIDGE_URL", "").strip().rstrip("/")
CAMERA_NAME = os.getenv("CAMERA_NAME", "Камера 1")
# Имя объекта / площадки на сервере (группировка камер и статус по объекту). Пусто = «Без объекта».
SITE_NAME = os.getenv("SITE_NAME", "").strip()
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")
VIOLATION_CLASSES = {name.strip().lower() for name in os.getenv("VIOLATION_CLASSES", "").split(",") if name.strip()}
VIOLATION_COOLDOWN_SECONDS = float(os.getenv("VIOLATION_COOLDOWN_SECONDS", "20"))
STREAM_INTERVAL_SECONDS = float(os.getenv("STREAM_INTERVAL_SECONDS", "0.5"))
HEARTBEAT_INTERVAL_SECONDS = float(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "5"))
# Пауза между камерами в одном цикле heartbeat (снимает «салvo» запросов).
HEARTBEAT_STAGGER_SECONDS = float(os.getenv("HEARTBEAT_STAGGER_SECONDS", "0.35"))
# Как в old/main.py: пауза после полного цикла «кадр → инференс → отправка» (снижает частоту HTTP).
CYCLE_PAUSE_SECONDS = float(os.getenv("CYCLE_PAUSE_SECONDS", "2"))
# Сохранять ли нарушения локально на диске клиента
SAVE_VIOLATIONS_LOCALLY = os.getenv("SAVE_VIOLATIONS_LOCALLY", "false").strip().lower() in ("1", "true", "yes")

# Оптимизация: когда сервер просит стрим (time.time() последнего запроса от сервера)
requested_streams: dict[str, float] = {}
# Режим mdb: случайная задержка перед стартом потока камеры (разносит пики по времени).
MDB_THREAD_START_JITTER_MAX = float(os.getenv("MDB_THREAD_START_JITTER_MAX", "2"))
USE_MDB_CAMERAS = os.getenv("USE_MDB_CAMERAS", "").strip().lower() in ("1", "true", "yes")
# Своя модель + Rules (как old/main.py, best.pt, Person / Red uniform)
USE_TRAINED_MODEL = os.getenv("USE_TRAINED_MODEL", "").strip().lower() in ("1", "true", "yes")
TRAINED_CONF_THRESHOLD = float(os.getenv("TRAINED_CONF_THRESHOLD", "0.5"))
# Сегментация + HSV по Colors (ещё один legacy-режим)
USE_COLOR_VIOLATIONS = os.getenv("USE_COLOR_VIOLATIONS", "").strip().lower() in ("1", "true", "yes")
SEG_CONF_THRESHOLD = float(os.getenv("SEG_CONF_THRESHOLD", "0.7"))

# RTSP: таймаут открытия (мс), как в старом main.py
RTSP_OPEN_TIMEOUT_MS = int(os.getenv("RTSP_OPEN_TIMEOUT_MS", "10000"))
# Сколько первых кадров выбросить после открытия (стабилизация буфера; только не webcam)
RTSP_WARMUP_FRAMES = int(os.getenv("RTSP_WARMUP_FRAMES", "5"))
# Периодически пересоздавать поток (сброс декодера H.264), 0 = выкл.
RTSP_RECONNECT_SECONDS = float(os.getenv("RTSP_RECONNECT_SECONDS", "0") or 0)
# Как старый load_image_from_rtsp: каждый кадр — новое открытие/закрытие (медленнее, но часто без артефактов)
RTSP_USE_SNAPSHOT = os.getenv("RTSP_USE_SNAPSHOT", "").strip().lower() in ("1", "true", "yes")

API_HEADERS = {"X-API-Token": API_TOKEN}

PIG_COUNT_ENABLED = os.getenv("PIG_COUNT_ENABLED", "").strip().lower() in ("1", "true", "yes")
PIG_COUNT_MODEL_PATH = os.getenv("PIG_COUNT_MODEL_PATH", "").strip() or YOLO_MODEL_PATH
PIG_COUNT_DB_PATH = os.getenv("PIG_COUNT_DB_PATH", os.getenv("SQLITE_DB_PATH", "users.db")).strip()
PIG_COUNT_LINE_Y_RATIO = float(os.getenv("PIG_COUNT_LINE_Y_RATIO", "0.58"))
PIG_COUNT_INFER_INTERVAL_SECONDS = float(os.getenv("PIG_COUNT_INFER_INTERVAL_SECONDS", "0.5"))
PIG_COUNT_CONF_THRESHOLD = float(os.getenv("PIG_COUNT_CONF_THRESHOLD", "0.35"))
PIG_COUNT_BATCH_GAP_SECONDS = float(os.getenv("PIG_COUNT_BATCH_GAP_SECONDS", "10"))
PIG_COUNT_DIRECTION = "up"
PIG_COUNT_CLASS_ID_RAW = (os.getenv("PIG_COUNT_CLASS_ID") or "").strip()
PIG_COUNT_CLASS_ID = int(PIG_COUNT_CLASS_ID_RAW) if PIG_COUNT_CLASS_ID_RAW else None
PIG_COUNT_CLASS_NAME = (os.getenv("PIG_COUNT_CLASS_NAME") or "").strip()


@dataclass
class _PigTrackState:
    last_cy: float
    counted: bool = False


@dataclass
class _PigCounterRuntime:
    line_y_ratio: float
    camera_name: str
    states: dict[int, _PigTrackState]
    pending_count: int = 0
    batch_started_ts: float = 0.0
    batch_last_ts: float = 0.0
    last_infer_ts: float = 0.0
    last_preview_bytes: bytes | None = None


def _load_pig_camera_allowlist_from_db(db_path_raw: str) -> set[str]:
    p = Path(expanded(db_path_raw)).resolve()
    if not p.is_file():
        print(f"[PigCount] users.db не найден: {p}")
        return set()
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pig_count_cameras (
                camera_name TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))
            )
            """
        )
        conn.commit()
        rows = conn.execute(
            "SELECT camera_name FROM pig_count_cameras WHERE enabled = 1"
        ).fetchall()
        return {_safe_camera_name(r["camera_name"]) for r in rows if str(r["camera_name"] or "").strip()}
    except sqlite3.Error as e:
        print(f"[PigCount] Ошибка чтения pig_count_cameras: {e}")
        return set()
    finally:
        if conn is not None:
            conn.close()


def _use_edge_bridge() -> bool:
    return bool(EDGE_BRIDGE_URL)


def _should_send_stream_now(camera_name: str, now_ts: float) -> bool:
    # В bridge-режиме preview нужен локально на edge всегда,
    # поэтому не ждём server-side stream_requested.
    if _use_edge_bridge():
        return True
    return (now_ts - requested_streams.get(camera_name, 0.0)) < 15.0


def _edge_checks_csv() -> str:
    # Не навязываем проверки из клиента в edge.
    # Реальная настройка "что делает камера" задаётся оператором в edge UI.
    return ""


def _open_video_capture_raw(source: str) -> cv2.VideoCapture:
    s = source.strip()
    if s.isdigit():
        return cv2.VideoCapture(int(s))
    try:
        return cv2.VideoCapture(
            s,
            apiPreference=cv2.CAP_ANY,
            params=[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, RTSP_OPEN_TIMEOUT_MS],
        )
    except TypeError:
        return cv2.VideoCapture(s)


def _is_network_stream(source: str) -> bool:
    s = source.strip().lower()
    return s.startswith(("rtsp://", "http://", "https://"))


def use_snapshot_mode(source: str) -> bool:
    return RTSP_USE_SNAPSHOT and _is_network_stream(source) and not source.strip().isdigit()


def grab_frame_snapshot(source: str):
    """Один кадр, как в старом load_image_from_rtsp: open → read → release."""
    cap = _open_video_capture_raw(source)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def _safe_camera_name(name: str | None) -> str:
    s = (name or "").strip()
    if not s or s.lower() == "none":
        return "Камера"
    return s


def _api_scope_data(camera_name: str) -> dict:
    return {"camera_name": _safe_camera_name(camera_name), "site_name": SITE_NAME}


def _camera_rule_summary(camera_id: int | None) -> str:
    if not USE_TRAINED_MODEL or camera_id is None:
        return "Правило: по violation-классам (VIOLATION_CLASSES)"

    policy_person = (os.getenv("POLICY_CLASS_PERSON") or "Person").strip()
    policy_uniform = (os.getenv("POLICY_CLASS_UNIFORM") or "Red uniform").strip()
    raw_ids = (os.getenv("POLICY_COLOR_IDS") or "2,6,7").replace(" ", "")
    try:
        policy_ids = tuple(int(x) for x in raw_ids.split(",") if x)
    except ValueError:
        policy_ids = ()
    if not policy_ids:
        policy_ids = (2, 6, 7)
    placeholders = ",".join("?" * len(policy_ids))
    db_path = os.getenv("SQLITE_DB_PATH", "users.db")
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT 1 FROM Rules
            WHERE camera_id = ? AND color_id IN ({placeholders}) AND access_granted = 0
            LIMIT 1
            """,
            (camera_id, *policy_ids),
        )
        if cur.fetchone():
            return f"Запрещающая зона: разрешен только класс '{policy_person}'"

        cur.execute(
            f"""
            SELECT 1 FROM Rules
            WHERE camera_id = ? AND color_id IN ({placeholders}) AND access_granted = 1
            LIMIT 1
            """,
            (camera_id, *policy_ids),
        )
        if cur.fetchone():
            return f"Разрешающая зона: разрешен только класс '{policy_uniform}'"
        return f"Правило не задано: разрешен только класс '{policy_person}'"
    except sqlite3.Error:
        return "Ошибка чтения Rules (users.db)"
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def send_heartbeat(camera_name: str, rule_summary: str = "", camera_address: str = "") -> None:
    try:
        if _use_edge_bridge():
            r = requests.post(
                f"{EDGE_BRIDGE_URL}/api/local/heartbeat",
                params={
                    "camera_name": _safe_camera_name(camera_name),
                    "rule_summary": rule_summary,
                    "camera_address": camera_address or "",
                    "checks_csv": _edge_checks_csv(),
                },
                timeout=5,
            )
        else:
            r = requests.post(
                f"{SERVER_URL}/api/heartbeat",
                headers=API_HEADERS,
                data={**_api_scope_data(camera_name), "rule_summary": rule_summary},
                timeout=5,
            )
        if r.status_code >= 400:
            target = "EDGE_BRIDGE_URL" if _use_edge_bridge() else "SERVER_URL/API_TOKEN"
            print(f"[Heartbeat] {camera_name}: HTTP {r.status_code} — проверьте {target}")
        else:
            try:
                data = r.json()
                if data.get("stream_requested"):
                    requested_streams[camera_name] = time.time()
            except Exception:
                pass
    except requests.RequestException as exc:
        print(f"[Heartbeat] {camera_name}: {exc}")


def send_heartbeat_loop(
    camera_names: list[str],
    stop_event: threading.Event,
    rule_map: dict[str, str] | None = None,
    source_map: dict[str, str] | None = None,
) -> None:
    rm = rule_map or {}
    sm = source_map or {}
    while not stop_event.is_set():
        # Батч: один запрос на все камеры (резко меньше коннектов к shared hosting)
        items = []
        for name in camera_names:
            items.append(
                {
                    "camera_name": _safe_camera_name(name),
                    "rule_summary": rm.get(name, ""),
                    "camera_address": sm.get(name, ""),
                    "checks_csv": _edge_checks_csv(),
                }
            )
        try:
            if _use_edge_bridge():
                requests.post(
                    f"{EDGE_BRIDGE_URL}/api/local/heartbeat_batch",
                    json={"items": items},
                    timeout=8,
                )
            else:
                # Прямо на сайт (если edge не используется)
                requests.post(
                    f"{SERVER_URL}/api/heartbeat_batch",
                    headers=API_HEADERS,
                    json={"items": [{**_api_scope_data(x['camera_name']), "rule_summary": x["rule_summary"]} for x in items]},
                    timeout=8,
                )
        except requests.RequestException as exc:
            print(f"[HeartbeatBatch] {exc}")

        stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)


def detect_violation_class_mode(results) -> tuple[bool, str]:
    if not results or not results[0].boxes:
        return False, "нарушение не обнаружено"

    boxes = results[0].boxes
    class_names = results[0].names
    class_ids = boxes.cls.tolist()

    detected_labels = [class_names.get(int(cls_id), "").lower() for cls_id in class_ids]
    for label in detected_labels:
        if label in VIOLATION_CLASSES:
            return True, f"Обнаружен класс: {label}"
    return False, "нарушение не обнаружено"


def draw_boxes(frame, results):
    if not results:
        return frame
    return results[0].plot()


def send_stream_frame(frame_bytes: bytes, camera_name: str, rule_summary: str = "", camera_address: str = "") -> None:
    try:
        files = {"frame": ("frame.jpg", frame_bytes, "image/jpeg")}
        if _use_edge_bridge():
            data = {
                "camera_name": _safe_camera_name(camera_name),
                "rule_summary": rule_summary,
                "camera_address": camera_address or "",
                "checks_csv": _edge_checks_csv(),
            }
            r = requests.post(f"{EDGE_BRIDGE_URL}/api/local/stream_frame", data=data, files=files, timeout=8)
        else:
            data = {**_api_scope_data(camera_name), "rule_summary": rule_summary}
            r = requests.post(f"{SERVER_URL}/api/stream_frame", headers=API_HEADERS, data=data, files=files, timeout=8)
        if r.status_code >= 400:
            target = "EDGE_BRIDGE_URL" if _use_edge_bridge() else "SERVER_URL/API_TOKEN"
            print(f"[Stream] {camera_name}: HTTP {r.status_code} — проверьте {target}")
    except requests.RequestException as exc:
        print(f"[Stream] {camera_name}: {exc}")


def send_violation(frame_bytes: bytes, violation_type: str, camera_name: str) -> None:
    if SAVE_VIOLATIONS_LOCALLY:
        try:
            out_dir = Path("violations_local")
            out_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_cam = "".join(c for c in camera_name if c.isalnum() or c in " -_").strip() or "cam"
            filepath = out_dir / f"{ts}_{safe_cam}.jpg"
            filepath.write_bytes(frame_bytes)
        except Exception as e:
            print(f"[LocalSave] Ошибка сохранения {camera_name}: {e}")

    try:
        files = {"image": ("violation.jpg", frame_bytes, "image/jpeg")}
        if _use_edge_bridge():
            data = {"camera_name": _safe_camera_name(camera_name), "violation_type": violation_type}
            r = requests.post(f"{EDGE_BRIDGE_URL}/api/local/enqueue", data=data, files=files, timeout=10)
        else:
            data = {**_api_scope_data(camera_name), "violation_type": violation_type}
            r = requests.post(f"{SERVER_URL}/api/violation", headers=API_HEADERS, data=data, files=files, timeout=10)
        if r.status_code >= 400:
            if _use_edge_bridge():
                print(f"[Violation] {camera_name}: HTTP {r.status_code} — ошибка EDGE_BRIDGE_URL. Тело: {r.text[:300]}")
            else:
                print(
                    f"[Violation] {camera_name}: HTTP {r.status_code} — на сайте не появится запись. "
                    f"Часто: неверный SERVER_URL (нужен подкаталог как ROOT_PATH на сервере), неверный API_TOKEN. Тело: {r.text[:300]}"
                )
    except requests.RequestException as exc:
        print(f"[Violation] {camera_name}: {exc}")


def _should_use_pig_detection(cls_id: int, names: dict[int, str]) -> bool:
    if PIG_COUNT_CLASS_ID is not None:
        return cls_id == PIG_COUNT_CLASS_ID
    if PIG_COUNT_CLASS_NAME:
        return names.get(cls_id, "").strip().lower() == PIG_COUNT_CLASS_NAME.lower()
    return True


def send_pig_count_event(
    *,
    camera_name: str,
    count: int,
    ts_from: float,
    ts_to: float,
    preview_bytes: bytes | None,
) -> None:
    if count <= 0:
        return
    payload = {
        "camera_name": _safe_camera_name(camera_name),
        "count": int(count),
        "direction": PIG_COUNT_DIRECTION,
        "line_y_ratio": PIG_COUNT_LINE_Y_RATIO,
        "ts_from": float(ts_from),
        "ts_to": float(ts_to),
    }
    files = {}
    if preview_bytes:
        files = {"preview": ("pig_preview.jpg", preview_bytes, "image/jpeg")}
    try:
        if _use_edge_bridge():
            r = requests.post(
                f"{EDGE_BRIDGE_URL}/api/local/pig_count_event",
                data={k: str(v) for k, v in payload.items()},
                files=files or None,
                timeout=10,
            )
        else:
            r = requests.post(
                f"{SERVER_URL}/api/pig_count",
                headers=API_HEADERS,
                data={**_api_scope_data(camera_name), **{k: str(v) for k, v in payload.items() if k != "camera_name"}},
                files=files or None,
                timeout=10,
            )
        if r.status_code >= 400:
            print(f"[PigCount] {camera_name}: HTTP {r.status_code} {r.text[:250]}")
        else:
            print(f"[PigCount] {camera_name}: отправлено count={count}")
    except requests.RequestException as exc:
        print(f"[PigCount] {camera_name}: {exc}")


def pig_count_tick(
    *,
    runtime: _PigCounterRuntime,
    model: YOLO,
    model_lock: threading.Lock,
    frame,
    now_ts: float,
) -> None:
    if (now_ts - runtime.last_infer_ts) < max(0.05, PIG_COUNT_INFER_INTERVAL_SECONDS):
        if (
            runtime.pending_count > 0
            and runtime.batch_last_ts > 0
            and (now_ts - runtime.batch_last_ts) >= max(2.0, PIG_COUNT_BATCH_GAP_SECONDS)
        ):
            send_pig_count_event(
                camera_name=runtime.camera_name,
                count=runtime.pending_count,
                ts_from=runtime.batch_started_ts or runtime.batch_last_ts,
                ts_to=runtime.batch_last_ts,
                preview_bytes=runtime.last_preview_bytes,
            )
            runtime.pending_count = 0
            runtime.batch_started_ts = 0.0
            runtime.batch_last_ts = 0.0
            runtime.last_preview_bytes = None
        return

    runtime.last_infer_ts = now_ts
    h = int(frame.shape[0]) if getattr(frame, "shape", None) is not None else 0
    if h <= 0:
        return
    line_y = int(max(0, min(h - 1, runtime.line_y_ratio * h)))

    with model_lock:
        results = model.track(
            source=frame,
            persist=True,
            verbose=False,
            conf=PIG_COUNT_CONF_THRESHOLD,
            tracker="bytetrack.yaml",
            device="cpu",
        )
    res = results[0]
    names = res.names if isinstance(res.names, dict) else {}
    new_crosses = 0
    if res.boxes is not None and res.boxes.id is not None:
        ids = res.boxes.id.int().cpu().tolist()
        xyxy = res.boxes.xyxy.cpu().tolist()
        cls_ids = res.boxes.cls.int().cpu().tolist()
        for tid, box, cls_id in zip(ids, xyxy, cls_ids):
            if not _should_use_pig_detection(int(cls_id), names):
                continue
            _x1, y1, _x2, y2 = box
            cy = (y1 + y2) / 2.0
            st = runtime.states.get(int(tid))
            crossed = False
            if st is not None and not st.counted:
                crossed = st.last_cy > line_y >= cy
            if crossed:
                st.counted = True
                new_crosses += 1
            if st is None:
                runtime.states[int(tid)] = _PigTrackState(last_cy=cy, counted=False)
            else:
                st.last_cy = cy

    if new_crosses > 0:
        runtime.pending_count += new_crosses
        if runtime.batch_started_ts <= 0:
            runtime.batch_started_ts = now_ts
        runtime.batch_last_ts = now_ts
        ok_prev, prev_buf = cv2.imencode(".jpg", frame)
        runtime.last_preview_bytes = prev_buf.tobytes() if ok_prev else runtime.last_preview_bytes

    if (
        runtime.pending_count > 0
        and runtime.batch_last_ts > 0
        and (now_ts - runtime.batch_last_ts) >= max(2.0, PIG_COUNT_BATCH_GAP_SECONDS)
    ):
        send_pig_count_event(
            camera_name=runtime.camera_name,
            count=runtime.pending_count,
            ts_from=runtime.batch_started_ts or runtime.batch_last_ts,
            ts_to=runtime.batch_last_ts,
            preview_bytes=runtime.last_preview_bytes,
        )
        runtime.pending_count = 0
        runtime.batch_started_ts = 0.0
        runtime.batch_last_ts = 0.0
        runtime.last_preview_bytes = None


def open_capture(source: str):
    """Постоянное соединение: webcam, файл или RTSP (с прогревом кадров)."""
    cap = _open_video_capture_raw(source)
    if not cap.isOpened():
        raise RuntimeError(f"Не удалось открыть источник: {source!r}")
    if not source.strip().isdigit():
        for _ in range(max(0, RTSP_WARMUP_FRAMES)):
            cap.read()
    return cap


class VideoSource:
    """Чтение кадров: постоянный поток или режим «снимок» (старый main.py)."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.snapshot = use_snapshot_mode(source)
        self.cap: cv2.VideoCapture | None = None
        self._opened_at = 0.0
        if not self.snapshot:
            self._reopen()

    def _reopen(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self.cap = open_capture(self.source)
        self._opened_at = time.time()

    def read(self) -> tuple[bool, object]:
        if self.snapshot:
            frame = grab_frame_snapshot(self.source)
            if frame is None:
                return False, None
            return True, frame
        assert self.cap is not None
        if (
            RTSP_RECONNECT_SECONDS > 0
            and not self.source.strip().isdigit()
            and time.time() - self._opened_at > RTSP_RECONNECT_SECONDS
        ):
            self._reopen()
        return self.cap.read()

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def camera_loop(
    camera_name: str,
    source: str,
    model: YOLO,
    model_lock: threading.Lock,
    stop_event: threading.Event,
    camera_id: int | None = None,
    rule_summary: str = "",
    pig_runtime: _PigCounterRuntime | None = None,
    pig_model: YOLO | None = None,
    pig_model_lock: Any | None = None,
) -> None:
    try:
        src = VideoSource(source)
    except RuntimeError as e:
        print(f"[{camera_name}] {e}")
        return

    if use_snapshot_mode(source):
        print(f"[{camera_name}] RTSP_USE_SNAPSHOT: режим как в старом load_image_from_rtsp (открытие на кадр)")

    if USE_TRAINED_MODEL:
        if camera_id is None:
            print(f"[{camera_name}] USE_TRAINED_MODEL: нет camera_id — пропуск.")
            src.release()
            return
    elif USE_COLOR_VIOLATIONS:
        if camera_id is None:
            print(f"[{camera_name}] USE_COLOR_VIOLATIONS: нет camera_id — пропуск.")
            src.release()
            return

    last_stream_sent = 0.0
    last_violation_sent = 0.0

    if USE_TRAINED_MODEL:
        from trained_model_rules import annotate_trained_violations
    elif USE_COLOR_VIOLATIONS:
        from color_rules import annotate_color_violations

    try:
        while not stop_event.is_set():
            ok, frame = src.read()
            if not ok or frame is None:
                if not src.snapshot:
                    print(f"[{camera_name}] Кадр не получен, повтор...")
                time.sleep(0.2)
                continue

            if USE_TRAINED_MODEL:
                with model_lock:
                    processed, has_violation, detected_type = annotate_trained_violations(
                        frame, camera_id, model, TRAINED_CONF_THRESHOLD
                    )
            elif USE_COLOR_VIOLATIONS:
                with model_lock:
                    processed, has_violation, detected_type = annotate_color_violations(
                        frame, camera_id, model, SEG_CONF_THRESHOLD
                    )
            else:
                with model_lock:
                    results = model.predict(source=frame, conf=0.35, verbose=False)
                processed = draw_boxes(frame, results)
                has_violation, detected_type = detect_violation_class_mode(results)

            ok_jpg, buffer = cv2.imencode(".jpg", processed)
            if not ok_jpg:
                continue
            frame_bytes = buffer.tobytes()

            now = time.time()
            if pig_runtime is not None and pig_model is not None and pig_model_lock is not None:
                pig_count_tick(
                    runtime=pig_runtime,
                    model=pig_model,
                    model_lock=pig_model_lock,
                    frame=frame,
                    now_ts=now,
                )
            if now - last_stream_sent >= STREAM_INTERVAL_SECONDS:
                # Без bridge: on-demand от сервера. С bridge: отправляем для локального preview.
                if _should_send_stream_now(camera_name, now):
                    send_stream_frame(frame_bytes, camera_name, rule_summary, source)
                    last_stream_sent = now

            if has_violation and (now - last_violation_sent >= VIOLATION_COOLDOWN_SECONDS):
                send_violation(frame_bytes, detected_type or "Нарушение", camera_name)
                last_violation_sent = now
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {camera_name}: {detected_type}")

            if CYCLE_PAUSE_SECONDS > 0:
                stop_event.wait(CYCLE_PAUSE_SECONDS)
    finally:
        src.release()


def _chdir_for_sqlite() -> None:
    parent = (os.getenv("MDB_PARENT_DIR") or "").strip()
    if parent:
        os.chdir(Path(expanded(parent)).resolve())
        print(f"Рабочий каталог для users.db: {os.getcwd()}")


def _parse_camera_id_env() -> int | None:
    raw = (os.getenv("CAMERA_ID") or "").strip()
    if not raw:
        return None
    return int(raw)


def run_single_camera_mode() -> None:
    print(f"Запуск QRPass Client (одна камера). Имя: {CAMERA_NAME}")
    if USE_TRAINED_MODEL or USE_COLOR_VIOLATIONS:
        _chdir_for_sqlite()
        cid = _parse_camera_id_env()
        if cid is None:
            print("Задайте в .env CAMERA_ID (id строки в таблице Cameras) для режима обученной модели или цветов.")
            return
    if use_snapshot_mode(CAMERA_SOURCE):
        print("RTSP_USE_SNAPSHOT: режим как в старом load_image_from_rtsp — открытие потока на каждый кадр.")
    if USE_TRAINED_MODEL:
        print("USE_TRAINED_MODEL: политика как в old/main.py (веса + Rules).")
    model = YOLO(YOLO_MODEL_PATH)
    pig_runtime: _PigCounterRuntime | None = None
    pig_model: YOLO | None = None
    pig_model_lock: Any | None = None
    if PIG_COUNT_ENABLED:
        allow = _load_pig_camera_allowlist_from_db(PIG_COUNT_DB_PATH)
        if _safe_camera_name(CAMERA_NAME) in allow:
            pig_runtime = _PigCounterRuntime(
                line_y_ratio=PIG_COUNT_LINE_Y_RATIO,
                camera_name=_safe_camera_name(CAMERA_NAME),
                states={},
            )
            pig_model = YOLO(PIG_COUNT_MODEL_PATH)
            pig_model_lock = threading.Lock()
            print(f"[PigCount] single-camera enabled: {CAMERA_NAME}, model={PIG_COUNT_MODEL_PATH}")
        else:
            print(f"[PigCount] {CAMERA_NAME}: не включена в pig_count_cameras, подсчет выключен.")
    try:
        src = VideoSource(CAMERA_SOURCE)
    except RuntimeError as e:
        print(e)
        return

    camera_id_single: int | None = None
    rule_summary_single = "Правило: по violation-классам (VIOLATION_CLASSES)"
    if USE_TRAINED_MODEL or USE_COLOR_VIOLATIONS:
        camera_id_single = _parse_camera_id_env()
        assert camera_id_single is not None
        rule_summary_single = _camera_rule_summary(camera_id_single)

    if USE_TRAINED_MODEL:
        from trained_model_rules import annotate_trained_violations
    elif USE_COLOR_VIOLATIONS:
        from color_rules import annotate_color_violations

    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=send_heartbeat_loop,
        args=([CAMERA_NAME], stop_event, {CAMERA_NAME: rule_summary_single}, {CAMERA_NAME: CAMERA_SOURCE}),
        daemon=True,
    )
    heartbeat_thread.start()

    last_stream_sent = 0.0
    last_violation_sent = 0.0

    try:
        while True:
            ok, frame = src.read()
            if not ok or frame is None:
                if not src.snapshot:
                    print("Кадр не получен, повтор...")
                time.sleep(0.2)
                continue

            if USE_TRAINED_MODEL:
                processed, has_violation, detected_type = annotate_trained_violations(
                    frame, camera_id_single, model, TRAINED_CONF_THRESHOLD
                )
            elif USE_COLOR_VIOLATIONS:
                processed, has_violation, detected_type = annotate_color_violations(
                    frame, camera_id_single, model, SEG_CONF_THRESHOLD
                )
            else:
                results = model.predict(source=frame, conf=0.35, verbose=False)
                processed = draw_boxes(frame, results)
                has_violation, detected_type = detect_violation_class_mode(results)

            ok_jpg, buffer = cv2.imencode(".jpg", processed)
            if not ok_jpg:
                continue
            frame_bytes = buffer.tobytes()

            now = time.time()
            if pig_runtime is not None and pig_model is not None and pig_model_lock is not None:
                pig_count_tick(
                    runtime=pig_runtime,
                    model=pig_model,
                    model_lock=pig_model_lock,
                    frame=frame,
                    now_ts=now,
                )
            if now - last_stream_sent >= STREAM_INTERVAL_SECONDS:
                # Без bridge: on-demand от сервера. С bridge: отправляем для локального preview.
                if _should_send_stream_now(CAMERA_NAME, now):
                    send_stream_frame(frame_bytes, CAMERA_NAME, rule_summary_single, CAMERA_SOURCE)
                    last_stream_sent = now

            if has_violation and (now - last_violation_sent >= VIOLATION_COOLDOWN_SECONDS):
                send_violation(frame_bytes, detected_type or "Нарушение", CAMERA_NAME)
                last_violation_sent = now
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Отправлено нарушение: {detected_type}")

            if CYCLE_PAUSE_SECONDS > 0:
                time.sleep(CYCLE_PAUSE_SECONDS)

    except KeyboardInterrupt:
        print("Остановка клиента...")
    finally:
        stop_event.set()
        src.release()


def run_mdb_cameras_mode() -> None:
    from mdb_runtime import ensure_database, load_mdb_module

    _chdir_for_sqlite()

    mdb = load_mdb_module()
    ensure_database(mdb)
    rows = mdb.get_cameras()
    if not rows:
        print("mdb: в Cameras нет записей — добавьте камеры (Telegram-бот / SQLite) и перезапустите.")
        return

    # Ожидаем кортежи (id, url, name) как в вашем mdb.py
    # В реальных БД часто name=NULL или повторяется: даем стабильные уникальные имена.
    def _display_name(raw_name: object, cam_id: int, used: set[str]) -> str:
        base = (str(raw_name or "").strip() if raw_name is not None else "")
        if not base or base.lower() in ("none", "null"):
            base = f"Камера #{cam_id}"
        name = base
        i = 2
        while name in used:
            name = f"{base} ({i})"
            i += 1
        used.add(name)
        return name

    cameras: list[tuple[int, str, str]] = []
    used_names: set[str] = set()
    for row in rows:
        if len(row) >= 3:
            cam_id = int(row[0])
            cam_url = str(row[1])
            cam_name = _display_name(row[2], cam_id, used_names)
            cameras.append((cam_id, cam_url, cam_name))
        else:
            print(f"Пропуск строки камеры (ожидалось id, url, name): {row}")

    if not cameras:
        return

    names = [c[2] for c in cameras]
    rule_map = {name: _camera_rule_summary(cid if USE_TRAINED_MODEL else None) for cid, _, name in cameras}
    print(f"Режим mdb: камер {len(cameras)} — {', '.join(names)}")
    if USE_TRAINED_MODEL:
        print("USE_TRAINED_MODEL: обученная YOLO + политика Rules (как old/main.py).")
    elif USE_COLOR_VIOLATIONS:
        print("USE_COLOR_VIOLATIONS: сегментация + HSV + Rules.")

    model = YOLO(YOLO_MODEL_PATH)
    model_lock = threading.Lock()
    pig_allow: set[str] = set()
    pig_model: YOLO | None = None
    pig_model_lock: Any | None = None
    if PIG_COUNT_ENABLED:
        pig_allow = _load_pig_camera_allowlist_from_db(PIG_COUNT_DB_PATH)
        if pig_allow:
            pig_model = YOLO(PIG_COUNT_MODEL_PATH)
            pig_model_lock = threading.Lock()
            print(f"[PigCount] enabled for {len(pig_allow)} cameras, model={PIG_COUNT_MODEL_PATH}")
        else:
            print("[PigCount] список камер пуст — подсчет отключен.")
    stop_event = threading.Event()

    heartbeat_thread = threading.Thread(
        target=send_heartbeat_loop,
        args=(names, stop_event, rule_map, {name: url for _cid, url, name in cameras}),
        daemon=True,
    )
    heartbeat_thread.start()

    def _start_one_camera(cid: int, url: str, name: str) -> None:
        if MDB_THREAD_START_JITTER_MAX > 0:
            time.sleep(random.uniform(0, MDB_THREAD_START_JITTER_MAX))
        pig_runtime: _PigCounterRuntime | None = None
        if pig_model is not None and pig_model_lock is not None and _safe_camera_name(name) in pig_allow:
            pig_runtime = _PigCounterRuntime(
                line_y_ratio=PIG_COUNT_LINE_Y_RATIO,
                camera_name=_safe_camera_name(name),
                states={},
            )
        camera_loop(
            name,
            url,
            model,
            model_lock,
            stop_event,
            camera_id=cid if (USE_TRAINED_MODEL or USE_COLOR_VIOLATIONS) else None,
            rule_summary=rule_map.get(name, ""),
            pig_runtime=pig_runtime,
            pig_model=pig_model,
            pig_model_lock=pig_model_lock,
        )

    for cid, url, name in cameras:
        threading.Thread(
            target=_start_one_camera,
            args=(cid, url, name),
            daemon=True,
        ).start()

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Остановка клиента (mdb)...")
    finally:
        stop_event.set()


def expanded(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def main() -> None:
    if USE_TRAINED_MODEL and USE_COLOR_VIOLATIONS:
        print("Замечание: USE_TRAINED_MODEL и USE_COLOR_VIOLATIONS — активна только обученная модель.")
    if USE_MDB_CAMERAS:
        run_mdb_cameras_mode()
    else:
        run_single_camera_mode()


if __name__ == "__main__":
    main()
