from views.base_view import JsonView


class ResourceView(JsonView):
    def created(self, record):
        return self.respond(201, self._body(record, "created"))

    def updated(self, record):
        return self.respond(200, self._body(record, "updated"))

    @staticmethod
    def _body(record, verb):
        body = {"status": "success", record.resource.key: record.key,
                "message": f"{record.resource.label} {verb}"}
        if record.extras:                       # tell the sender which unmapped keys we kept
            body["extra_fields_stored"] = sorted(record.extras)
        return body
