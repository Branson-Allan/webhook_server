"""Front controller: dispatches requests and turns every failure into a response."""
import logging

from core.exceptions import HttpError, InternalServerError
from core.http import Request, Response
from core.router import Router


class Application:
    def __init__(self, router: Router, error_view, logger=None):
        self._router = router
        self._error_view = error_view
        self._log = logger or logging.getLogger("app")

    def handle(self, request: Request) -> Response:
        try:
            return self._router.dispatch(request)
        except HttpError as exc:
            return self.render_error(exc)
        except Exception:
            self._log.exception("Unhandled error")
            return self.render_error(InternalServerError())

    def render_error(self, exc: HttpError) -> Response:
        return self._error_view.render(exc)
