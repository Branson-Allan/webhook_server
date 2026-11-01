"""Application configuration.

Settings are read from, in increasing priority:
  1. built-in defaults
  2. a .env file next to this module (or the file named by ENV_FILE)
  3. real environment variables
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SECRET = "change-me-please"
DEFAULT_ENV_FILE = Path(__file__).resolve().parent / ".env"


def parse_env_file(path) -> dict:
    """Parse a .env file into a dict. Missing file -> empty dict.

    Supported: KEY=value, KEY="quoted value", KEY='quoted value', `export KEY=value`,
    blank lines, full-line # comments, and trailing ' # comment' on unquoted values
    (quote the value if it must contain ' #').  Lines that are not valid assignments
    (e.g. text accidentally pasted into the file) are skipped with a warning instead
    of crashing the whole app at startup.
    """
    path = Path(path)
    values: dict = {}
    if not path.is_file():
        return values
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key.isidentifier():
            print(f"WARNING: {path}:{number}: ignoring malformed line "
                  f"(expected KEY=VALUE): {raw!r}")
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        values[key] = value
    return values


def _int_setting(env, key, default):
    """Read an integer setting; fall back to the default with a warning if the
    value is malformed (e.g. text accidentally pasted after it in .env)."""
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"WARNING: {key}={raw!r} is not a valid integer; using default {default}")
        return default


@dataclass(frozen=True)
class Config:
    client_id: str = "crm-client"
    client_secret: str = DEFAULT_SECRET
    token_ttl: int = 3600
    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "tickets.db"
    max_body_bytes: int = 1_000_000
    static_token: str = ""      # optional fixed access token (see .env.example)

    @classmethod
    def from_env(cls, environ=None, env_file=None) -> "Config":
        environ = os.environ if environ is None else environ
        path = env_file or environ.get("ENV_FILE") or DEFAULT_ENV_FILE
        env = {**parse_env_file(path), **environ}      # real env vars win over .env
        get = env.get
        return cls(
            client_id=get("CLIENT_ID", cls.client_id),
            client_secret=get("CLIENT_SECRET", cls.client_secret),
            token_ttl=_int_setting(env, "TOKEN_TTL", cls.token_ttl),
            host=get("HOST", cls.host),
            port=_int_setting(env, "PORT", cls.port),
            db_path=get("DB_PATH", cls.db_path),
            max_body_bytes=_int_setting(env, "MAX_BODY_BYTES", cls.max_body_bytes),
            static_token=get("STATIC_ACCESS_TOKEN", cls.static_token),
        )

    @property
    def uses_default_secret(self) -> bool:
        return self.client_secret == DEFAULT_SECRET