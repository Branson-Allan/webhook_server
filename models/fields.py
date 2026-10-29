"""Field types used to declare a resource's schema.

Each field validates/normalises an incoming JSON value and knows how to
store it in (and read it back from) the database.
"""
import copy
import json
from datetime import datetime


class FieldError(ValueError):
    """A value did not satisfy its field's rules."""


class Field:
    sql_type = "TEXT"
    keep_blank = False          # keep "" as "" instead of converting to NULL

    def __init__(self, required: bool = False, default=None):
        self.required = required
        self.default = default

    def process(self, value):
        """Return the normalised value, or raise FieldError."""
        if value is None and self.default is not None:
            value = copy.deepcopy(self.default)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if self.required:
                raise FieldError("is required")
            return "" if (self.keep_blank and isinstance(value, str)) else None
        return self.convert(value)

    def convert(self, value):                 # override in subclasses
        return value

    def to_db(self, value):
        return value

    def from_db(self, value):
        return value


class StringField(Field):
    """Accepts strings and numbers (stored as text)."""
    keep_blank = True

    def __init__(self, required=False, default=None, strip=False):
        super().__init__(required, default)
        self.strip = strip

    def convert(self, value):
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise FieldError("must be a string or number")
        value = str(value)
        return value.strip() if self.strip else value


class IntegerField(Field):
    sql_type = "INTEGER"

    def convert(self, value):
        if isinstance(value, bool):
            raise FieldError("must be an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                pass
        raise FieldError("must be an integer")


class FloatField(Field):
    sql_type = "REAL"

    def convert(self, value):
        if isinstance(value, bool):
            raise FieldError("must be a number")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                pass
        raise FieldError("must be a number")


class BooleanField(Field):
    sql_type = "INTEGER"
    _TRUE, _FALSE = {"true", "yes", "1"}, {"false", "no", "0"}

    def convert(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if text in self._TRUE:
                return True
            if text in self._FALSE:
                return False
        raise FieldError("must be a boolean")

    def to_db(self, value):
        return int(value)

    def from_db(self, value):
        return bool(value)


class DateTimeField(Field):
    def __init__(self, required=False, default=None,
                 fmt="%Y-%m-%d %H:%M:%S", label="YYYY-MM-DD HH:MM:SS"):
        super().__init__(required, default)
        self.fmt, self.label = fmt, label

    def convert(self, value):
        if not isinstance(value, str):
            raise FieldError(f"must match '{self.label}'")
        try:
            datetime.strptime(value.strip(), self.fmt)
        except ValueError:
            raise FieldError(f"must match '{self.label}'")
        return value.strip()


class JsonField(Field):
    """Any JSON value (object, list, number...), stored as JSON text."""

    def to_db(self, value):
        return json.dumps(value)

    def from_db(self, value):
        return json.loads(value)


class ObjectListField(JsonField):
    """A list of JSON objects, e.g. [{"Response Type": "Open"}]."""

    def convert(self, value):
        if not isinstance(value, list) or not all(isinstance(i, dict) for i in value):
            raise FieldError("must be a list of objects")
        return value
