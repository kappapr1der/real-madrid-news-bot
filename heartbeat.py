import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

from runtime_config import HEARTBEAT_PORT, get_log_file
from status_manager import health_snapshot, record_status

LOG_FILE = get_log_file("heartbeat.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)


class HeartbeatHandler(BaseHTTPRequestHandler):
    def write_health_response(self, include_body: bool = True) -> None:
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


def run(server_class=HTTPServer, handler_class=HeartbeatHandler, port=HEARTBEAT_PORT):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    logging.info(f"Starting Bernabeu Heartbeat on port {port}")
    record_status("heartbeat", "starting", f"port {port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    record_status("heartbeat", "stopped", "server stopped")
    logging.info("Stopping Bernabeu Heartbeat")


if __name__ == "__main__":
    run()
