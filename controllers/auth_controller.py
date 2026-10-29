from core.exceptions import BadRequest, Unauthorized
from core.http import Request
from services.auth_service import AuthService
from views.token_view import TokenView


class AuthController:
    """Token endpoint: the 'URL' the CRM calls for dynamic authorization."""

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
        if request.content_type == "application/json":
            data = request.json()
            if not isinstance(data, dict):
                raise BadRequest("Body must be a JSON object")
        else:
            data = request.form()
        return data.get("client_id"), data.get("client_secret")
