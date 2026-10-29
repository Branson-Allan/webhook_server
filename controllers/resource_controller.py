from core.exceptions import UnprocessableEntity, UnsupportedMediaType
from core.http import Request
from models.errors import ValidationError
from models.resource import Resource
from models.resource_repository import ResourceRepository
from views.resource_view import ResourceView


class ResourceController:
    """One generic webhook controller, instantiated once per Resource."""

    def __init__(self, resource: Resource, repository: ResourceRepository,
                 view: ResourceView):
        self._resource = resource
        self._repo = repository
        self._view = view

    def store(self, request: Request):
        if request.content_type != "application/json":
            raise UnsupportedMediaType()
        payload = request.json()
        try:
            record = self._resource.parse(payload, raw_text=request.text())
        except ValidationError as exc:
            raise UnprocessableEntity("Validation failed", errors=exc.errors)
        created = self._repo.save(record)
        return self._view.created(record) if created else self._view.updated(record)
