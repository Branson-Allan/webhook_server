"""TEMPLATE for a new webhook endpoint (ignored by the loader because of the
leading underscore).

To add an endpoint:
  1. Copy this file to resources/<your_name>.py
  2. Change `name`, `key` and `fields`
  3. Restart the app. POST /webhook/<name> now exists, protected by the same
     Bearer token, with its own table.

Schema-less shortcut: Resource("my_events") with no fields accepts ANY JSON
object, stores it in extra_fields and generates an `id` for every record.
"""
from models.fields import (BooleanField, DateTimeField, FloatField, IntegerField,
                           JsonField, ObjectListField, StringField)
from models.resource import EXTRA_STORE, Resource   # also: EXTRA_IGNORE, EXTRA_REJECT

RESOURCE = Resource(
    name="example_template",        # table name; default path is /webhook/example_template
    label="Example",                # used in response messages
    key="example_id",               # re-sending the same key updates the record (201 -> 200)
    extra=EXTRA_STORE,              # unknown keys: store (default) / ignore / reject (422)
    protected=True,                 # False = no Bearer token needed
    fields={
        "example_id": StringField(),
        "title": StringField(required=True),
        "quantity": IntegerField(),
        "price": FloatField(),
        "paid": BooleanField(),
        "placed_at": DateTimeField(),                 # 'YYYY-MM-DD HH:MM:SS'
        "lines": ObjectListField(default=[]),         # [{"sku": "A1"}, ...]
        "metadata": JsonField(),                      # any JSON value
    },
)
