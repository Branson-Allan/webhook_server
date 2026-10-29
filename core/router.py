"""Maps (method, path) to a controller action, running middleware first."""
from dataclasses import dataclass
from typing import Callable

from core.exceptions import MethodNotAllowed, NotFound
from core.http import Request, Response


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    handler: Callable[[Request], Response]
    middleware: tuple = ()


class Router:
    def __init__(self):
        self._routes: list[Route] = []

    def add(self, method, path, handler, middleware=()):
        self._routes.append(Route(method.upper(), path, handler, tuple(middleware)))
        return self

    def get(self, path, handler, middleware=()):
        return self.add("GET", path, handler, middleware)

    def post(self, path, handler, middleware=()):
        return self.add("POST", path, handler, middleware)

    def dispatch(self, request: Request) -> Response:
        candidates = [r for r in self._routes if r.path == request.path]
        if not candidates:
            raise NotFound()
        route = next((r for r in candidates if r.method == request.method), None)
        if route is None:
            raise MethodNotAllowed(sorted({r.method for r in candidates}))
        for check in route.middleware:
            check(request)
        return route.handler(request)
