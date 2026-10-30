from core.exceptions import Unauthorized
from core.http import Request
from services.auth_service import AuthService


class BearerAuth:
    """Route guard: requires a valid access token (Bearer header, bare Authorization
    value, or X-Access-Token header)."""

    def __init__(self, auth_service: AuthService):
        self._auth = auth_service

    def __call__(self, request: Request) -> None:
        token = request.access_token()
        if not token or not self._auth.is_token_valid(token):
            raise Unauthorized()