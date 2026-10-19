import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlsplit(self.path).path not in ("/", "/health"):
            self.send_error(404)
            return

        response = b"1"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: object) -> None:
        pass


def keep_alive(port: int | None = None) -> ThreadingHTTPServer:

    server_port = port if port is not None else int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", server_port), HealthHandler)
    Thread(target=server.serve_forever, name="keep-alive", daemon=True).start()
    return server