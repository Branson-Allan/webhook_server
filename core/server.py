"""Adapter between the stdlib HTTP server and Application."""
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from core.application import Application
from core.exceptions import BadRequest, HttpError, PayloadTooLarge
from core.http import Request, Response


_SECRET_PARAMS = re.compile(
    r"(?i)\b(client_secret|access_token|token|api_key|secret)=[^&\s\"']+")


def redact(text: str) -> str:
    """Hide secret query-string values before they reach the logs."""
    return _SECRET_PARAMS.sub(lambda m: f"{m.group(1)}=***", text)


class HttpServer:
    def __init__(self, app: Application, host: str, port: int,
                 max_body_bytes: int, logger=None):
        self._app = app
        self._max_body = max_body_bytes
        self._log = logger or logging.getLogger("http")
        self._httpd = ThreadingHTTPServer((host, port), self._make_handler())

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    def serve_forever(self):
        self._httpd.serve_forever()

    def shutdown(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    def _make_handler(self):
        app, max_body, log = self._app, self._max_body, self._log

        class Handler(BaseHTTPRequestHandler):
            server_version = "CRMWebhook/2.0"

            def _dispatch(self):
                try:
                    response = app.handle(self._build_request())
                except HttpError as exc:      # problems reading the request itself
                    self.close_connection = True
                    response = app.render_error(exc)
                self._write(response)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _dispatch

            def _build_request(self) -> Request:
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    raise BadRequest("Invalid Content-Length")
                if length < 0:
                    raise BadRequest("Invalid Content-Length")
                if length > max_body:
                    self._discard(min(length, max_body * 10))
                    raise PayloadTooLarge()
                body = self.rfile.read(length) if length else b""
                path, _, query_string = self.path.partition("?")
                query = {k: v[0] for k, v in
                         parse_qs(query_string, keep_blank_values=True).items()}
                return Request(self.command, path, self.headers, body, query)

            def _discard(self, remaining: int):
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)

            def _write(self, response: Response):
                self.send_response(response.status)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(response.body)))
                self.end_headers()
                self.wfile.write(response.body)

            def log_message(self, fmt, *args):
                log.info("%s - %s", self.address_string(), redact(fmt % args))

        return Handler