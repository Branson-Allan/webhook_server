from core.exceptions import BadRequest, Unauthorized
from core.http import Request
from services.auth_service import AuthService
from views.token_view import TokenView


class AuthController:
    """Authorization URL: the CRM calls this (GET or POST) to obtain an access token.

    Client credentials may arrive as HTTP Basic, a JSON body, a form body, or
    ?client_id=...&client_secret=... in the URL itself.
    """

    def __init__(self, auth_service: AuthService, view: TokenView):
        self._auth = auth_service
        self._view = view

    def token(self, request: Request):
        client_id, client_secret = self._credentials(request)
        if not self._auth.verify_client(client_id, client_secret):
            raise Unauthorized("Invalid client credentials")
        return self._view.show(self._auth.issue_token())

    @staticmethod
    def _credentials(request: Request):
        basic = request.basic_credentials()
        if basic:
            return basic
        data = {}
        if request.body.strip():
            if request.content_type == "application/json":
                data = request.json()
                if not isinstance(data, dict):
                    raise BadRequest("Body must be a JSON object")
            else:
                data = request.form()
        client_id = data.get("client_id") or request.query.get("client_id")
        client_secret = data.get("client_secret") or request.query.get("client_secret")
        return client_id, client_secret