"""Framework-neutral Request / Response objects."""
import base64
import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from core.exceptions import BadRequest


@dataclass
class Request:
    method: str
    path: str
    headers: dict
    body: bytes = b""
    query: dict = field(default_factory=dict)

    def __post_init__(self):
        self.headers = {k.lower(): v for k, v in self.headers.items()}

    def header(self, name, default=None):
        return self.headers.get(name.lower(), default)

    @property
    def content_type(self) -> str:
        return (self.header("content-type") or "").split(";")[0].strip().lower()

    def text(self) -> str:
        try:
            return self.body.decode("utf-8")
        except UnicodeDecodeError:
            raise BadRequest("Body must be UTF-8")

    def json(self):
        try:
            return json.loads(self.text())
        except json.JSONDecodeError:
            raise BadRequest("Invalid JSON")

    def form(self) -> dict:
        return {k: v[0] for k, v in parse_qs(self.text()).items()}

    def access_token(self):
        """The caller's token, however the CRM sends it:
        'Authorization: Bearer <t>', 'Authorization: Token <t>',
        a bare 'Authorization: <t>', or an 'X-Access-Token: <t>' header."""
        auth = (self.header("authorization") or "").strip()
        if auth:
            scheme, _, value = auth.partition(" ")
            if value.strip() and scheme.lower() in ("bearer", "token"):
                return value.strip()
            if " " not in auth:
                return auth
        return (self.header("x-access-token") or "").strip() or None

    def basic_credentials(self):
        scheme, _, value = (self.header("authorization") or "").partition(" ")
        if scheme.lower() != "basic":
            return None
        try:
            user, sep, password = base64.b64decode(value).decode().partition(":")
        except Exception:
            return None
        return (user, password) if sep else None


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict = field(default_factory=dict)