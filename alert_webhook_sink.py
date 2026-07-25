"""Local HTTP receiver for verifying SigNoz alert notifications."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


LOG_PATH = Path(__file__).with_name("alert_webhook_events.log")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        LOG_PATH.write_text(body + "\n", encoding="utf-8")
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


HTTPServer(("0.0.0.0", 9001), Handler).serve_forever()
