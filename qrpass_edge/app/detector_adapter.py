"""
Адаптер для интеграции edge с любым детектором.

Использование в вашем процессе:

    from app.detector_adapter import EdgeDetectorAdapter

    edge = EdgeDetectorAdapter(camera_name="ФФО-1")
    edge.heartbeat_if_due()
    edge.send_preview_frame(Path("./preview.jpg"))
    edge.enqueue_violation(Path("./shot.jpg"), "Нет униформы")
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from app import queue_db
from app.config import settings
from app.hashfile import sha256_file
from app.uploader import post_heartbeat, post_stream_frame


class EdgeDetectorAdapter:
    def __init__(
        self,
        *,
        camera_name: str | None = None,
        site_name: str | None = None,
        queue_db_path: Path | None = None,
    ) -> None:
        self.camera_name = (camera_name or settings.default_camera_name).strip()
        self.site_name = (site_name or settings.site_name).strip()
        self.queue_db_path = queue_db_path or settings.queue_db_path
        self._last_heartbeat_at = 0.0

    def _connect(self):
        conn = queue_db.connect(self.queue_db_path)
        queue_db.init_schema(conn)
        return conn

    def heartbeat_if_due(self, *, force: bool = False, rule_summary: str = "edge-online") -> bool:
        interval = float(settings.heartbeat_interval_seconds or 0.0)
        now = time.time()
        due = force or interval <= 0 or (now - self._last_heartbeat_at) >= interval
        if not due:
            return True
        r = post_heartbeat(
            camera_name=self.camera_name,
            site_name=self.site_name,
            rule_summary=rule_summary,
        )
        if r.ok:
            self._last_heartbeat_at = now
        return r.ok

    def send_preview_frame(self, frame_path: Path, *, rule_summary: str = "") -> bool:
        r = post_stream_frame(
            frame_path=frame_path.resolve(),
            camera_name=self.camera_name,
            site_name=self.site_name,
            rule_summary=rule_summary,
        )
        return r.ok

    def enqueue_violation(
        self,
        image_path: Path,
        violation_type: str,
        *,
        copy_to_storage: bool = True,
    ) -> bool:
        src = image_path.resolve()
        if not src.is_file():
            raise FileNotFoundError(str(src))

        target = src
        if copy_to_storage:
            settings.storage_root.mkdir(parents=True, exist_ok=True)
            suffix = src.suffix or ".jpg"
            dst = settings.storage_root / f"q_{int(time.time() * 1000)}_{src.stem}{suffix}"
            shutil.copy2(src, dst)
            target = dst.resolve()

        digest = sha256_file(target)
        conn = self._connect()
        try:
            return queue_db.enqueue_violation(
                conn,
                camera_name=self.camera_name,
                violation_type=violation_type.strip(),
                file_path=target,
                file_sha256=digest,
            )
        finally:
            conn.close()
