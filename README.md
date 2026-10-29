# CRM Webhook (MVC, extensible)

    cp .env.example .env        # Windows: copy .env.example .env
    # edit .env: set CLIENT_ID and CLIENT_SECRET once
    python app.py
    python -m unittest discover -v

Settings priority: real environment variables > `.env` file > built-in defaults.
`.env` is read from the project folder regardless of where you launch Python from
(override the location with `ENV_FILE=/path/to/file`).

Auth: `POST /auth/token` (client_id + client_secret) -> Bearer token for every protected webhook.

## 1. Send extra, unplanned keys
Just send them. Any key not declared in the resource's schema is saved as JSON in the
`extra_fields` column, and the response lists them under `extra_fields_stored`.
Query them with SQLite JSON functions:

    SELECT ticket_id, json_extract(extra_fields, '$.vip') FROM tickets;

Re-sending a record (same key) replaces its `extra_fields` with the latest set.
Per-resource control: `extra="store"` (default) | `"ignore"` | `"reject"` (422).

## 2. Promote a key to a real typed column
Add one line to the `fields` dict in `resources/<name>.py`, e.g. `"vip": BooleanField()`.
On the next start the table gets the new column automatically (existing rows are kept).
Field types: StringField, IntegerField, FloatField, BooleanField, DateTimeField,
JsonField, ObjectListField. Options: `required=True`, `default=...`.

## 3. Add an entirely new endpoint
Copy `resources/_template.py` to `resources/<name>.py`, edit name/key/fields, restart.
`POST /webhook/<name>` exists with its own table and the same Bearer auth. No other
file changes. `Resource("name")` with no fields accepts any JSON and generates an `id`.

Other Resource options: `path="/custom/url"`, `protected=False`, `label="Order"`.
