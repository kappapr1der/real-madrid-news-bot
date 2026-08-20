import json
import logging
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from runtime_config import HEARTBEAT_HOST, HEARTBEAT_PORT, HEARTBEAT_TOKEN, get_log_file
from status_manager import health_snapshot, record_status

REQUEST_TIMEOUT_SECONDS = 5

LOG_FILE = get_log_file("heartbeat.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)


class ResilientHeartbeatServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(REQUEST_TIMEOUT_SECONDS)
        return request, client_address

    def handle_error(self, request, client_address):
        logging.warning("Ignored broken heartbeat request from %s", client_address[0])


class HeartbeatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logging.info("%s - %s", self.address_string(), format % args)

    def authorized(self) -> bool:
        if not HEARTBEAT_TOKEN:
            return True

        header_token = self.headers.get("X-Heartbeat-Token", "")
        query_token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        return secrets.compare_digest(header_token, HEARTBEAT_TOKEN) or secrets.compare_digest(
            query_token,
            HEARTBEAT_TOKEN,
        )

    def write_forbidden_response(self, include_body: bool = True) -> None:
        body = b'{"ok": false, "error": "forbidden"}\n'
        self.send_response(403)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body) if include_body else 0))
        self.end_headers()
        if include_body:
            self.wfile.write(body)
        logging.warning("%s %s - Heartbeat forbidden", self.command, self.path)

    def write_health_response(self, include_body: bool = True) -> None:
        if not self.authorized():
            self.write_forbidden_response(include_body=include_body)
            return

        payload, status_code = health_snapshot()
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body) if include_body else 0))
        self.end_headers()
        if include_body:
            self.wfile.write(body)
        record_status(
            "heartbeat",
            "ok" if status_code == 200 else "degraded",
            "health request served",
            {"status_code": status_code, "issues": len(payload.get("issues", []))},
        )
        logging.info("%s %s - Heartbeat responded %s", self.command, self.path, status_code)

    def do_GET(self):
        self.write_health_response(include_body=True)

    def do_HEAD(self):
        self.write_health_response(include_body=False)


def run(server_class=ResilientHeartbeatServer, handler_class=HeartbeatHandler, port=HEARTBEAT_PORT):
    server_address = (HEARTBEAT_HOST, port)
    httpd = server_class(server_address, handler_class)
    logging.info(f"Starting Bernabeu Heartbeat on {HEARTBEAT_HOST}:{port}")
    record_status("heartbeat", "starting", f"{HEARTBEAT_HOST}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    record_status("heartbeat", "stopped", "server stopped")
    logging.info("Stopping Bernabeu Heartbeat")


if __name__ == "__main__":
    run()
