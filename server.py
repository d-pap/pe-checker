"""Local web server and daily source sync for PE Checker."""

from __future__ import annotations

import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from core import DB_PATH, connect, lookup, refresh

ROOT = Path(__file__).parent.resolve()
PORT = int(os.environ.get("PORT", "4173"))
sync_lock = threading.Lock()
sync_state = {"running": False, "last_result": None}


def refresh_in_background(force=False):
    if not sync_lock.acquire(blocking=False):
        return

    def run():
        sync_state["running"] = True
        try:
            db = connect()
            try:
                sync_state["last_result"] = refresh(db, force=force)
            finally:
                db.close()
        finally:
            sync_state["running"] = False
            sync_lock.release()

    threading.Thread(target=run, name="source-refresh", daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/api/status":
            db = connect()
            try:
                rows = [dict(row) for row in db.execute("SELECT * FROM source_sync ORDER BY source")]
            finally:
                db.close()
            self.send_json({"sources": rows, "sync": sync_state})
            return
        if parsed.path == "/api/check":
            params = parse_qs(parsed.query)
            name = (params.get("name") or [""])[0].strip()[:120]
            place = (params.get("place") or [""])[0].strip()[:120]
            if not name and not place:
                self.send_json({"error": "Enter a business name or place."}, 400)
                return
            db = connect()
            try:
                answer = lookup(db, name, place)
            finally:
                db.close()
            self.send_json(answer)
            return
        relative = "live.html" if parsed.path == "/" else parsed.path.lstrip("/")
        target = (ROOT / relative).resolve()
        if target.parent != ROOT or target.suffix not in {".html", ".css", ".js", ".svg"}:
            self.send_error(404)
            return
        try:
            payload = target.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

if __name__ == "__main__":
    db = connect()
    db.close()
    refresh_in_background()
    def scheduled_refresh():
        while True:
            threading.Event().wait(3600)
            refresh_in_background()

    threading.Thread(target=scheduled_refresh, name="refresh-schedule", daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"PE Checker: http://localhost:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
