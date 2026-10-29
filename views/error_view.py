from views.base_view import JsonView


class ErrorView(JsonView):
    def render(self, exc):
        payload = {"status": "error", "message": exc.message}
        if exc.errors:
            payload["errors"] = exc.errors
        return self.respond(exc.status, payload, exc.headers)
