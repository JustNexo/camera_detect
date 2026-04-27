"""
Утилита для интеграции детектора с edge-сервисом:
  - heartbeat на сайт
  - отправка preview-кадра в /api/stream_frame

Примеры:
  python -m app.edge_sync heartbeat --camera "ФФО-1"
  python -m app.edge_sync frame --camera "ФФО-1" --file ./preview.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import settings
from app.uploader import post_heartbeat, post_stream_frame


def _print(result: dict) -> int:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Edge sync helper (heartbeat/frame)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hb = sub.add_parser("heartbeat", help="Отправить heartbeat на сервер")
    p_hb.add_argument("--camera", default=settings.default_camera_name)
    p_hb.add_argument("--rule-summary", default="")

    p_fr = sub.add_parser("frame", help="Отправить preview-кадр на сервер")
    p_fr.add_argument("--camera", default=settings.default_camera_name)
    p_fr.add_argument("--file", required=True, type=Path)
    p_fr.add_argument("--rule-summary", default="")

    args = parser.parse_args()

    if args.cmd == "heartbeat":
        r = post_heartbeat(camera_name=args.camera.strip(), site_name=settings.site_name, rule_summary=args.rule_summary)
        return _print({"ok": r.ok, "http_code": r.http_code, "message": r.message})

    if args.cmd == "frame":
        f = args.file.resolve()
        r = post_stream_frame(
            frame_path=f,
            camera_name=args.camera.strip(),
            site_name=settings.site_name,
            rule_summary=args.rule_summary,
        )
        return _print({"ok": r.ok, "http_code": r.http_code, "message": r.message, "file": str(f)})

    print(json.dumps({"ok": False, "error": "unknown_command"}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
