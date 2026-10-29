"""Resource = a declarative description of one webhook payload type.

A Resource says: its name/endpoint, which fields are typed and validated,
which key identifies a record, and what to do with keys it does not know.
"""
import json
import re
import uuid

from models.errors import ValidationError
from models.fields import Field, FieldError, StringField

EXTRA_STORE = "store"     # keep unknown keys in the extra_fields JSON column (default)
EXTRA_IGNORE = "ignore"   # silently drop unknown keys
EXTRA_REJECT = "reject"   # answer 422 if unknown keys are sent

RESERVED_COLUMNS = ("extra_fields", "raw_payload", "received_at", "updated_at")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Resource:
    def __init__(self, name: str, fields: dict | None = None, key: str | None = None,
                 path: str | None = None, table: str | None = None,
                 label: str | None = None, extra: str = EXTRA_STORE,
                 protected: bool = True):
        self.name = self._identifier(name, "name")
        self.table = self._identifier(table or name, "table")
        self.path = path or f"/webhook/{name}"
        if not self.path.startswith("/"):
            raise ValueError("path must start with '/'")
        self.label = label or name.replace("_", " ").title()
        if extra not in (EXTRA_STORE, EXTRA_IGNORE, EXTRA_REJECT):
            raise ValueError(f"unknown extra mode: {extra!r}")
        self.extra = extra
        self.protected = protected

        self.fields: dict[str, Field] = dict(fields or {})
        for column in self.fields:
            self._identifier(column, "field")
            if column in RESERVED_COLUMNS:
                raise ValueError(f"field name {column!r} is reserved")
        self.auto_key = key is None
        if self.auto_key:                     # no natural key: generate an id per record
            self.key = "id"
            self.fields.setdefault("id", StringField())
        else:
            if key not in self.fields:
                raise ValueError(f"key {key!r} is not a declared field")
            self.key = key
            self.fields[key].required = True

    @staticmethod
    def _identifier(value: str, what: str) -> str:
        if not isinstance(value, str) or not _IDENTIFIER.match(value):
            raise ValueError(f"invalid {what} {value!r}: use letters, digits and underscores")
        return value

    def parse(self, payload, raw_text: str = "") -> "Record":
        """Validate a payload and return a Record, or raise ValidationError."""
        if not isinstance(payload, dict):
            raise ValidationError({"body": "must be a JSON object"})
        values, errors = {}, {}
        for name, field in self.fields.items():
            try:
                values[name] = field.process(payload.get(name))
            except FieldError as exc:
                errors[name] = str(exc)
        unknown = {k: v for k, v in payload.items() if k not in self.fields}
        if unknown and self.extra == EXTRA_REJECT:
            errors.update({k: "unknown field" for k in unknown})
        if errors:
            raise ValidationError(errors)
        if self.auto_key and not values[self.key]:
            values[self.key] = uuid.uuid4().hex
        extras = unknown if self.extra == EXTRA_STORE else {}
        return Record(self, values, extras, raw_text)


class Record:
    """One validated payload, ready to be stored."""

    def __init__(self, resource: Resource, values: dict, extras: dict, raw_payload: str):
        self.resource = resource
        self.values = values
        self.extras = extras
        self.raw_payload = raw_payload

    @property
    def key(self):
        return self.values[self.resource.key]

    def to_row(self, now: str) -> dict:
        row = {}
        for name, field in self.resource.fields.items():
            value = self.values.get(name)
            row[name] = None if value is None else field.to_db(value)
        row.update(extra_fields=json.dumps(self.extras), raw_payload=self.raw_payload,
                   received_at=now, updated_at=now)
        return row
