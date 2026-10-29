import json

from core.http import Response


class JsonView:
    """Base view: serialises a payload into a JSON Response."""

    def respond(self, status: int, payload, headers=None) -> Response:
        body = json.dumps(payload).encode("utf-8")
        merged = {"Content-Type": "application/json"}
        merged.update(headers or {})
        return Response(status, body, merged)
