import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG_FILE = "logs/heartbeat.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

class HeartbeatHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bernabeu Heartbeat OK")
        logging.info("GET / - Heartbeat responded 200")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        logging.info("HEAD / - Heartbeat responded 200")

def run(server_class=HTTPServer, handler_class=HeartbeatHandler, port=8000):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    logging.info(f"Starting Bernabeu Heartbeat on port {port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info("Stopping Bernabeu Heartbeat")

if __name__ == "__main__":
    run()
