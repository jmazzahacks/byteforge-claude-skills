"""Isolated synthetic backend shared by the tests and benchmark.

No production URL or credential is accepted. Delays occur in independent server
threads so the blocking reference cannot stall its own backend event loop.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
from urllib.parse import parse_qs, urlsplit


class Backend(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 256

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.records = []
        self.lock = threading.Lock()
        self.started = threading.Event()
        self.release = threading.Event()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def do_GET(self):
        query = parse_qs(urlsplit(self.path).query)
        mode = query.get("mode", ["fast"])[0]
        auth = self.headers.get("Authorization", "")
        identity = auth.removeprefix("Bearer ")
        with self.server.lock:
            self.server.records.append({"authorization": auth, "cookie": self.headers.get("Cookie"),
                                        "query": query, "mode": mode})
        self.server.started.set()
        if mode == "hold":
            self.server.release.wait(5)
        time.sleep(min(max(float(query.get("delay", [0])[0]), 0), 2))
        status = 503 if mode == "error" else 307 if mode == "redirect" else 200
        payload = json.dumps({"identity": identity, "mode": mode}).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Set-Cookie", "backend_session=fixture-only; Path=/")
            if status == 307:
                self.send_header("Location", "/work?mode=fast")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Expected in cancellation and read-timeout cases.

    def log_message(self, *_):
        pass


@contextmanager
def backend():
    server = Backend()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
