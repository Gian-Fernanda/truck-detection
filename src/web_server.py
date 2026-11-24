import json
import os
import mimetypes
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from typing import Optional

from src.engine import VideoEngine
from src.config import BASE_DIR


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class DashboardHTTPHandler(SimpleHTTPRequestHandler):
    engine: Optional[VideoEngine] = None

    def __init__(self, *args, **kwargs):
        # Set base directory for static file serving
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        # 1. Main Dashboard HTML
        if self.path in ("/", "/index.html"):
            html_path = BASE_DIR / "templates" / "index.html"
            if html_path.exists():
                with open(html_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
                return

        # 2. MJPEG Live Video Feed
        elif self.path == "/video_feed":
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()

            try:
                while self.engine and self.engine.running:
                    frame_bytes = self.engine.get_latest_frame()
                    if frame_bytes is not None:
                        self.wfile.write(b"--FRAME\r\n")
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(frame_bytes)))
                        self.end_headers()
                        self.wfile.write(frame_bytes)
                        self.wfile.write(b"\r\n")
                    time.sleep(0.033)  # ~30 FPS
            except (ConnectionResetError, BrokenPipeError):
                pass
            return

        # 3. Real-time Telemetry & Stats API
        elif self.path == "/api/stats":
            stats = self.engine.get_stats() if self.engine else {}
            payload = json.dumps(stats).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(payload)
            return

        # 4. Download CSV Log
        elif self.path == "/api/export_csv":
            csv_path = BASE_DIR / "data" / "riwayat_truk_cy.csv"
            if csv_path.exists():
                with open(csv_path, "rb") as f:
                    csv_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=riwayat_truk_cy.csv")
                self.send_header("Content-Length", str(len(csv_data)))
                self.end_headers()
                self.wfile.write(csv_data)
                return
            else:
                self.send_error(404, "File CSV belum tersedia.")
                return

        # 5. Serve Static Assets (CSS, JS, etc.)
        elif self.path.startswith("/static/"):
            relative_path = self.path.lstrip("/")
            file_path = BASE_DIR / relative_path
            if file_path.exists() and file_path.is_file():
                mime_type, _ = mimetypes.guess_type(str(file_path))
                mime_type = mime_type or "application/octet-stream"
                with open(file_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(data)
                return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        # 1. Update Polygon Zone Points
        if self.path == "/api/zone":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                points = data.get("points", [])
                if len(points) >= 3 and self.engine:
                    self.engine.update_zone(points)
                    response = {"success": True, "message": "Zona CY berhasil diperbarui!"}
                else:
                    response = {"success": False, "message": "Minimal 3 titik untuk membuat area zona."}
            except Exception as e:
                response = {"success": False, "message": str(e)}

            res_bytes = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_bytes)))
            self.end_headers()
            self.wfile.write(res_bytes)
            return

        self.send_error(404, "Endpoint not found")

    def log_message(self, format, *args):
        # Suppress spamming terminal with video feed frame requests
        if args and any(x in str(args[0]) for x in ("/video_feed", "/api/stats", "/static/")):
            return
        super().log_message(format, *args)


def start_web_server(engine: VideoEngine, host: str = "0.0.0.0", port: int = 5000):
    """Starts the HTTP server for web dashboard monitoring."""
    DashboardHTTPHandler.engine = engine
    server = ThreadedHTTPServer((host, port), DashboardHTTPHandler)
    print(f"\n" + "=" * 60)
    print(f"  🌐 CY MONITORING WEB DASHBOARD BERHASIL AKTIF!")
    print(f"  🔗 Akses di browser: http://localhost:{port} atau http://127.0.0.1:{port}")
    print(f"=" * 60 + "\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Mematikan web server...")
    finally:
        server.server_close()
