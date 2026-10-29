class ValidationError(Exception):
    """Raised by models when data is invalid. Knows nothing about HTTP."""

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__("Validation failed")
