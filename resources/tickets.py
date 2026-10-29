"""CRM ticket payload  ->  POST /webhook/tickets

Any key NOT listed below is still accepted and saved in the extra_fields column.
To make a new key a real, typed column, just add it to `fields`
(the table is migrated automatically on the next start).
"""
from models.fields import DateTimeField, ObjectListField, StringField
from models.resource import Resource

RESOURCE = Resource(
    name="tickets",
    label="Ticket",
    key="ticket_id",
    fields={
        "ticket_id": StringField(strip=True),
        "customer_name": StringField(),
        "customer_email": StringField(),
        "customer_phone": StringField(),
        "customer_type": StringField(),
        "customer_rating": StringField(),
        "company": StringField(),
        "location": StringField(),
        "age": StringField(),
        "status": StringField(),
        "source": StringField(),
        "category": StringField(),
        "disposition": StringField(),
        "sub_disposition": StringField(),
        "comments": StringField(),
        "date_created": DateTimeField(),
        "ticket_closure_date": DateTimeField(),
        "created_by": StringField(),
        "assigned_to": StringField(),
        "asset_name": StringField(),
        "additional_variables": ObjectListField(default=[]),
    },
)
