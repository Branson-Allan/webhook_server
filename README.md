# CRM Webhook (MVC, extensible)

    cp .env.example .env        # Windows: copy .env.example .env
    # edit .env: set CLIENT_ID and CLIENT_SECRET once
    python app.py
    python -m unittest discover -v

Settings priority: real environment variables > `.env` file > built-in defaults.
`.env` is read from the project folder regardless of where you launch Python from
(override the location with `ENV_FILE=/path/to/file`).

Auth: `POST /auth/token` (client_id + client_secret) -> Bearer token for every protected webhook.

**No auth needed?** Set `AUTH_ENABLED=false` in `.env` and every webhook ingests data
with no token at all (the `/auth/token` endpoint keeps working, and valid Bearer
tokens are still accepted). Warning: anyone who can reach the URL can write data —
only disable auth on a trusted/private network or behind another gate (e.g. ngrok
basic auth / IP allowlist). Per-endpoint control is also available via
`protected=False` on a single Resource.

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

## Connecting a CRM whose form has only "Authorization URL" and "Access Token"

    python connection_info.py https://YOUR-DOMAIN.ngrok-free.app

prints both strings. Two cases:

1. **CRM fetches the token itself (Dynamic).**
   Authorization URL = `https://HOST/auth/token?client_id=...&client_secret=...`
   Access Token = `access_token` (the name of the response field holding the token;
   `token` and `accessToken` are also returned).
   The CRM may call the URL with GET or POST. Credentials can also be sent as HTTP Basic,
   JSON or form body.
2. **CRM wants a fixed token pasted in.** Set `STATIC_ACCESS_TOKEN` in `.env`
   (24+ random characters) and paste that value as the Access Token.

The webhook accepts the token as `Authorization: Bearer <t>`, `Authorization: Token <t>`,
a bare `Authorization: <t>`, or `X-Access-Token: <t>`.

The Authorization URL contains your client secret, so treat it like a password.
Secrets in query strings are redacted from this app's logs, but ngrok's local inspector
(127.0.0.1:4040) and the CRM's own settings will still show them.