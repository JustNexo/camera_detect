from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

from app.config import settings


@dataclass
class UploadResult:
    ok: bool
    http_code: int | None
    message: str


def _api_url(path: str) -> str:
    return f"{settings.server_url.rstrip('/')}/api/{path.lstrip('/')}"


def post_violation(
    *,
    file_path: Path,
    camera_name: str,
    violation_type: str,
    site_name: str,
    timeout: float = 120.0,
) -> UploadResult:
    if not settings.api_token:
        return UploadResult(False, None, "API_TOKEN пуст")

    url = _api_url("violation")
    headers = {"X-API-Token": settings.api_token}

    path = file_path
    if not path.is_file():
        return UploadResult(False, None, "Файл не найден")

    try:
        with path.open("rb") as f:
            files = {"image": (path.name, f, "application/octet-stream")}
            data = {
                "camera_name": camera_name,
                "violation_type": violation_type,
                "site_name": site_name or "",
            }
            r = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)
    except requests.RequestException as e:
        return UploadResult(False, None, str(e)[:2000])

    if r.status_code == 200:
        return UploadResult(True, 200, (r.text or "")[:500])
    return UploadResult(False, r.status_code, (r.text or r.reason or "error")[:2000])


def post_heartbeat(*, camera_name: str, site_name: str, rule_summary: str = "", timeout: float = 15.0) -> UploadResult:
    if not settings.api_token:
        return UploadResult(False, None, "API_TOKEN пуст")
    url = _api_url("heartbeat")
    headers = {"X-API-Token": settings.api_token}
    data = {
        "camera_name": camera_name,
        "site_name": site_name or "",
        "rule_summary": rule_summary or "",
    }
    try:
        r = requests.post(url, headers=headers, data=data, timeout=timeout)
    except requests.RequestException as e:
        return UploadResult(False, None, str(e)[:2000])
    if r.status_code == 200:
        return UploadResult(True, 200, (r.text or "")[:1000])
    return UploadResult(False, r.status_code, (r.text or r.reason or "error")[:2000])


def post_stream_frame(
    *,
    frame_path: Path,
    camera_name: str,
    site_name: str,
    rule_summary: str = "",
    timeout: float = 30.0,
) -> UploadResult:
    if not settings.api_token:
        return UploadResult(False, None, "API_TOKEN пуст")
    if not frame_path.is_file():
        return UploadResult(False, None, "Файл кадра не найден")
    url = _api_url("stream_frame")
    headers = {"X-API-Token": settings.api_token}
    data = {
        "camera_name": camera_name,
        "site_name": site_name or "",
        "rule_summary": rule_summary or "",
    }
    try:
        with frame_path.open("rb") as f:
            files = {"frame": (frame_path.name, f, "application/octet-stream")}
            r = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)
    except requests.RequestException as e:
        return UploadResult(False, None, str(e)[:2000])
    if r.status_code == 200:
        return UploadResult(True, 200, (r.text or "")[:1000])
    return UploadResult(False, r.status_code, (r.text or r.reason or "error")[:2000])


def post_pig_count_event(
    *,
    camera_name: str,
    site_name: str,
    count: int,
    ts_from: float,
    ts_to: float,
    direction: str = "up",
    line_y_ratio: float = 0.58,
    preview_path: Path | None = None,
    timeout: float = 30.0,
) -> UploadResult:
    if not settings.api_token:
        return UploadResult(False, None, "API_TOKEN пуст")
    url = _api_url("pig_count")
    headers = {"X-API-Token": settings.api_token}
    data = {
        "camera_name": camera_name,
        "site_name": site_name or "",
        "count": str(int(count)),
        "ts_from": str(float(ts_from)),
        "ts_to": str(float(ts_to)),
        "direction": str(direction or "up"),
        "line_y_ratio": str(float(line_y_ratio)),
    }
    try:
        if preview_path and preview_path.is_file():
            with preview_path.open("rb") as f:
                files = {"preview": (preview_path.name, f, "application/octet-stream")}
                r = requests.post(url, headers=headers, data=data, files=files, timeout=timeout)
        else:
            r = requests.post(url, headers=headers, data=data, timeout=timeout)
    except requests.RequestException as e:
        return UploadResult(False, None, str(e)[:2000])
    if r.status_code == 200:
        return UploadResult(True, 200, (r.text or "")[:1000])
    return UploadResult(False, r.status_code, (r.text or r.reason or "error")[:2000])


def ping_selfcheck(timeout: float = 15.0) -> UploadResult:
    if not settings.api_token:
        return UploadResult(False, None, "API_TOKEN пуст")
    url = _api_url("_debug/selfcheck")
    headers = {"X-API-Token": settings.api_token}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return UploadResult(False, None, str(e)[:2000])
    if r.status_code == 200:
        return UploadResult(True, 200, (r.text or "")[:2000])
    return UploadResult(False, r.status_code, (r.text or r.reason or "error")[:2000])
