from views.base_view import JsonView


class HealthView(JsonView):
    def show(self):
        return self.respond(200, {"status": "ok"})
