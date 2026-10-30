"""Business logic for client authentication and access-token lifecycle."""
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from models.token import TokenRepository


@dataclass(frozen=True)
class IssuedToken:
    value: str
    expires_in: int


class AuthService:
    def __init__(self, tokens: TokenRepository, client_id: str,
                 client_secret: str, token_ttl: int, clock=time.time,
                 static_token: str = ""):
        self._tokens = tokens
        self._client_id = client_id.encode()
        self._client_secret = client_secret.encode()
        self._ttl = token_ttl
        self._clock = clock
        self._static = static_token.encode()    # b"" = feature disabled

    def verify_client(self, client_id, client_secret) -> bool:
        if client_id is None or client_secret is None:
            return False
        id_ok = hmac.compare_digest(str(client_id).encode(), self._client_id)
        secret_ok = hmac.compare_digest(str(client_secret).encode(), self._client_secret)
        return id_ok and secret_ok

    def issue_token(self) -> IssuedToken:
        value = secrets.token_urlsafe(32)
        now = self._clock()
        self._tokens.add(self._hash(value), now + self._ttl, now)
        return IssuedToken(value, self._ttl)

    def is_token_valid(self, token: str) -> bool:
        if self._static and hmac.compare_digest(token.encode(), self._static):
            return True                          # fixed token from .env
        expires_at = self._tokens.expiry_of(self._hash(token))
        return expires_at is not None and expires_at > self._clock()

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()