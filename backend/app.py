"""Unified HTTP and WebMCP Bridge Server for Dynamic WebMCP Agent Network."""
import json
import logging
import mimetypes
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Set up project path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from backend.api.approvals import ApprovalsAPI
from backend.api.bridge import BridgeAPI
from backend.api.health import HealthAPI
from backend.api.tasks import TaskWorkflowAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("WebMCP.Server")

STATIC_DIR = BASE_DIR / "apps" / "demo-store"


class WebMCPServerHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS for WebMCP browser integrations
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-WebMCP-Session")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API Routes
        if path == "/api/health":
            self._send_json(HealthAPI.handle_health())
        elif path == "/api/tools":
            self._send_json(HealthAPI.handle_tools())
        elif path == "/api/products":
            self._send_json(HealthAPI.handle_products())
        elif path == "/api/bridge/sessions":
            self._send_json(BridgeAPI.handle_list_sessions())
        else:
            # Serve Static files from apps/demo-store
            self._serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        try:
            if path == "/api/bridge/register":
                res = BridgeAPI.handle_register(body)
                self._send_json(res)
            elif path == "/api/bridge/heartbeat":
                res = BridgeAPI.handle_heartbeat(body)
                self._send_json(res)
            elif path == "/api/tasks/run_workflow":
                res = TaskWorkflowAPI.handle_run_workflow(body)
                self._send_json(res)
            elif path == "/api/approvals/execute":
                res = ApprovalsAPI.handle_execute_approval(body)
                self._send_json(res)
            else:
                self.send_response(404)
                self._send_json({"error": "Endpoint not found"})
        except Exception as e:
            logger.error(f"Error handling POST {path}: {e}", exc_info=True)
            self.send_response(400)
            self._send_json({"status": "FAILED", "error": str(e)})

    def _read_json_body(self) -> dict:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            raw = self.rfile.read(content_len).decode("utf-8")
            try:
                return json.loads(raw)
            except Exception:
                return {}
        return {}

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: str):
        if path == "/" or path == "":
            path = "/index.html"

        # Sanitize path
        file_path = STATIC_DIR / path.lstrip("/")
        if file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            self.send_response(200)
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            content = file_path.read_bytes()
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self._send_json({"error": f"File '{path}' not found"})


def run_server(host: str = "127.0.0.1", port: int = 8000):
    server = ThreadingHTTPServer((host, port), WebMCPServerHandler)
    logger.info(f"Dynamic WebMCP Agent Network server listening at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down.")
        server.server_close()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")
    run_server(host=host, port=port)
