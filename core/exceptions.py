"""HTTP error hierarchy. Raising one of these anywhere yields the matching response."""


class HttpError(Exception):
    status = 500
    default_message = "Internal server error"

    def __init__(self, message=None, errors=None, headers=None):
        self.message = message or self.default_message
        self.errors = errors
        self.headers = dict(headers or {})
        super().__init__(self.message)


class BadRequest(HttpError):
    status = 400
    default_message = "Bad request"


class Unauthorized(HttpError):
    status = 401
    default_message = "Missing or invalid access token"

    def __init__(self, message=None, errors=None, headers=None):
        merged = {"WWW-Authenticate": 'Bearer realm="crm-webhook"'}
        merged.update(headers or {})
        super().__init__(message, errors, merged)


class NotFound(HttpError):
    status = 404
    default_message = "Not found"


class MethodNotAllowed(HttpError):
    status = 405

    def __init__(self, allowed):
        allowed = list(allowed)
        super().__init__(f"Method not allowed, use {', '.join(allowed)}",
                         headers={"Allow": ", ".join(allowed)})


class PayloadTooLarge(HttpError):
    status = 413
    default_message = "Payload too large"


class UnsupportedMediaType(HttpError):
    status = 415
    default_message = "Content-Type must be application/json"


class UnprocessableEntity(HttpError):
    status = 422
    default_message = "Validation failed"


class InternalServerError(HttpError):
    status = 500
