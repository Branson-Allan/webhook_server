from core.http import Request
from views.health_view import HealthView


class HealthController:
    def __init__(self, view: HealthView):
        self._view = view

    def index(self, request: Request):
        return self._view.show()
