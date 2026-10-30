import base64
import importlib
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace

from app import build_application
from config import Config
from core.server import HttpServer
from models.database import Database
from models.fields import (BooleanField, DateTimeField, FloatField, IntegerField,
                           ObjectListField, StringField)
from models.resource import EXTRA_IGNORE, EXTRA_REJECT, Resource
from models.resource_repository import ResourceRepository
from resources import discover, ensure_unique

SAMPLE = {
    "customer_name": "John Doe", "customer_email": "johndoe@example.com",
    "customer_phone": "12345678", "customer_type": "grages", "customer_rating": "4.5",
    "company": "ABC", "ticket_id": "12334", "location": "General Mathenge",
    "age": "age in hrs", "status": "Closed", "source": "email",
    "category": "general inquiry", "disposition": "job inquiry",
    "sub_disposition": "internship", "comments": "This is an example",
    "date_created": "2025-08-14 09:35:00", "ticket_closure_date": "2025-08-15 14:20:00",
    "created_by": "Jane Doe", "assigned_to": "John Dalton", "asset_name": "KBY105R",
    "additional_variables": [{"Response Type": "Open"}],
}


class ServerFixture:
    overrides = {}
    resources = None          # None = auto-discover from resources/

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls._tmp.name, "t.db")
        cfg = replace(Config(), client_id="crm", client_secret="s3cret", port=0,
                      db_path=cls.db_path, max_body_bytes=10_000, **cls.overrides)
        app = build_application(cfg, cls.resources)
        cls.server = HttpServer(app, cfg.host, 0, cfg.max_body_bytes)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls._tmp.cleanup()

    def call(self, method, path, body=None, headers=None, raw=None):
        headers = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers=headers)
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            resp = e
        return resp.getcode(), json.loads(resp.read() or b"null"), resp.headers

    def token(self):
        _, body, _ = self.call("POST", "/auth/token",
                               {"client_id": "crm", "client_secret": "s3cret"})
        return body["access_token"]

    def auth(self):
        return {"Authorization": f"Bearer {self.token()}"}

    def rows(self, sql, params=()):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, params)]
        finally:
            conn.close()


class TestAuthAndTickets(ServerFixture, unittest.TestCase):
    def test_health(self):
        self.assertEqual(self.call("GET", "/health")[0], 200)

    def test_token_json(self):
        code, body, _ = self.call("POST", "/auth/token",
                                  {"client_id": "crm", "client_secret": "s3cret"})
        self.assertEqual(code, 200)
        self.assertEqual(body["token_type"], "Bearer")
        self.assertEqual(body["expires_in"], 3600)

    def test_token_form_and_basic(self):
        code, _, _ = self.call("POST", "/auth/token", raw=b"client_id=crm&client_secret=s3cret")
        self.assertEqual(code, 200)
        basic = base64.b64encode(b"crm:s3cret").decode()
        code, _, _ = self.call("POST", "/auth/token", raw=b"",
                               headers={"Authorization": f"Basic {basic}"})
        self.assertEqual(code, 200)

    def test_token_bad_credentials(self):
        code, _, headers = self.call("POST", "/auth/token",
                                     {"client_id": "crm", "client_secret": "nope"})
        self.assertEqual(code, 401)
        self.assertIn("Bearer", headers["WWW-Authenticate"])

    def test_token_malformed_body(self):
        code, _, _ = self.call("POST", "/auth/token", raw=b"{bad",
                               headers={"Content-Type": "application/json"})
        self.assertEqual(code, 400)

    def test_create_then_update(self):
        payload = dict(SAMPLE, ticket_id="T-1")
        code, body, _ = self.call("POST", "/webhook/tickets", payload, self.auth())
        self.assertEqual((code, body["message"], body["ticket_id"]),
                         (201, "Ticket created", "T-1"))
        self.assertNotIn("extra_fields_stored", body)
        payload["status"] = "Open"
        code, body, _ = self.call("POST", "/webhook/tickets", payload, self.auth())
        self.assertEqual((code, body["message"]), (200, "Ticket updated"))
        row = self.rows("SELECT * FROM tickets WHERE ticket_id='T-1'")[0]
        self.assertEqual(row["status"], "Open")
        self.assertEqual(json.loads(row["additional_variables"]), [{"Response Type": "Open"}])
        self.assertEqual(json.loads(row["extra_fields"]), {})

    def test_extra_random_keys_are_stored(self):
        payload = dict(SAMPLE, ticket_id="X-1", vip=True, score=9.5,
                       nested={"a": [1, 2]}, **{"Custom Field": "hello"})
        code, body, _ = self.call("POST", "/webhook/tickets", payload, self.auth())
        self.assertEqual(code, 201)
        self.assertEqual(body["extra_fields_stored"],
                         ["Custom Field", "nested", "score", "vip"])
        row = self.rows("SELECT extra_fields, customer_name FROM tickets WHERE ticket_id='X-1'")[0]
        self.assertEqual(row["customer_name"], "John Doe")
        self.assertEqual(json.loads(row["extra_fields"]),
                         {"vip": True, "score": 9.5, "nested": {"a": [1, 2]},
                          "Custom Field": "hello"})
        # re-sending replaces the extras with the latest set
        self.call("POST", "/webhook/tickets", dict(payload, vip=None, score=None,
                  nested=None, **{"Custom Field": "bye"}), self.auth())
        row = self.rows("SELECT extra_fields FROM tickets WHERE ticket_id='X-1'")[0]
        self.assertEqual(json.loads(row["extra_fields"])["Custom Field"], "bye")

    def test_minimal_payload_with_only_key(self):
        code, body, _ = self.call("POST", "/webhook/tickets", {"ticket_id": 777}, self.auth())
        self.assertEqual((code, body["ticket_id"]), (201, "777"))

    def test_webhook_requires_token(self):
        self.assertEqual(self.call("POST", "/webhook/tickets", SAMPLE)[0], 401)
        bad = {"Authorization": "Bearer abc"}
        self.assertEqual(self.call("POST", "/webhook/tickets", SAMPLE, bad)[0], 401)

    def test_invalid_json(self):
        h = dict(self.auth(), **{"Content-Type": "application/json"})
        self.assertEqual(self.call("POST", "/webhook/tickets", raw=b"{oops", headers=h)[0], 400)

    def test_validation_errors(self):
        code, body, _ = self.call("POST", "/webhook/tickets",
                                  {"date_created": "x", "additional_variables": "no"},
                                  self.auth())
        self.assertEqual(code, 422)
        self.assertEqual(set(body["errors"]),
                         {"ticket_id", "date_created", "additional_variables"})

    def test_non_object_body(self):
        h = dict(self.auth(), **{"Content-Type": "application/json"})
        self.assertEqual(self.call("POST", "/webhook/tickets", raw=b"[1,2]", headers=h)[0], 422)

    def test_wrong_content_type(self):
        h = dict(self.auth(), **{"Content-Type": "text/plain"})
        self.assertEqual(self.call("POST", "/webhook/tickets", raw=b"hi", headers=h)[0], 415)

    def test_method_not_allowed(self):
        code, _, headers = self.call("PUT", "/webhook/tickets", raw=b"")
        self.assertEqual(code, 405)
        self.assertEqual(headers["Allow"], "POST")

    def test_not_found(self):
        self.assertEqual(self.call("GET", "/nope")[0], 404)

    def test_payload_too_large(self):
        h = dict(self.auth(), **{"Content-Type": "application/json"})
        code, _, _ = self.call("POST", "/webhook/tickets", raw=b"x" * 20_000, headers=h)
        self.assertEqual(code, 413)


ORDERS = Resource("orders", label="Order", key="order_id", fields={
    "order_id": IntegerField(), "customer": StringField(required=True),
    "total": FloatField(), "paid": BooleanField(), "placed_at": DateTimeField(),
    "items": ObjectListField(default=[]),
})
EVENTS = Resource("events")                                           # schema-less
STRICT = Resource("strict", key="sid", fields={"sid": StringField()}, extra=EXTRA_REJECT)
LENIENT = Resource("lenient", key="lid", fields={"lid": StringField()}, extra=EXTRA_IGNORE)
PUBLIC = Resource("public_ping", protected=False)
CUSTOM_PATH = Resource("legacy", path="/api/v1/legacy-hook", key="k", fields={"k": StringField()})


class TestNewEndpoints(ServerFixture, unittest.TestCase):
    resources = [ORDERS, EVENTS, STRICT, LENIENT, PUBLIC, CUSTOM_PATH]

    def test_typed_resource_with_coercion_and_extras(self):
        payload = {"order_id": "15", "customer": "Ann", "total": "19.99", "paid": "yes",
                   "placed_at": "2025-01-01 10:00:00", "coupon": "SAVE10"}
        code, body, _ = self.call("POST", "/webhook/orders", payload, self.auth())
        self.assertEqual((code, body["order_id"], body["message"]), (201, 15, "Order created"))
        self.assertEqual(body["extra_fields_stored"], ["coupon"])
        row = self.rows("SELECT * FROM orders WHERE order_id=15")[0]
        self.assertEqual((row["total"], row["paid"]), (19.99, 1))
        self.assertEqual(json.loads(row["extra_fields"]), {"coupon": "SAVE10"})
        self.assertEqual(self.call("POST", "/webhook/orders", payload, self.auth())[0], 200)

    def test_typed_resource_validation(self):
        code, body, _ = self.call("POST", "/webhook/orders",
                                  {"order_id": "abc", "total": "x", "paid": "maybe",
                                   "placed_at": "nope"}, self.auth())
        self.assertEqual(code, 422)
        self.assertEqual(set(body["errors"]),
                         {"order_id", "customer", "total", "paid", "placed_at"})

    def test_schemaless_resource_accepts_anything_and_generates_id(self):
        _, a, _ = self.call("POST", "/webhook/events", {"type": "click", "x": 1}, self.auth())
        _, b, _ = self.call("POST", "/webhook/events", {"type": "click", "x": 1}, self.auth())
        self.assertEqual(len(a["id"]), 32)
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(a["extra_fields_stored"], ["type", "x"])
        self.assertEqual(len(self.rows("SELECT * FROM events")), 2)
        code, _, _ = self.call("POST", "/webhook/events", {"id": "abc", "a": 1}, self.auth())
        self.assertEqual(code, 201)
        code, _, _ = self.call("POST", "/webhook/events", {"id": "abc", "a": 2}, self.auth())
        self.assertEqual(code, 200)

    def test_reject_mode(self):
        code, body, _ = self.call("POST", "/webhook/strict",
                                  {"sid": "1", "other": 2}, self.auth())
        self.assertEqual((code, body["errors"]), (422, {"other": "unknown field"}))
        self.assertEqual(self.call("POST", "/webhook/strict", {"sid": "1"}, self.auth())[0], 201)

    def test_ignore_mode(self):
        code, body, _ = self.call("POST", "/webhook/lenient",
                                  {"lid": "1", "junk": 2}, self.auth())
        self.assertEqual(code, 201)
        self.assertNotIn("extra_fields_stored", body)
        self.assertEqual(self.rows("SELECT extra_fields FROM lenient")[0]["extra_fields"], "{}")

    def test_unprotected_and_custom_path(self):
        self.assertEqual(self.call("POST", "/webhook/public_ping", {"a": 1})[0], 201)
        self.assertEqual(self.call("POST", "/webhook/orders", {"customer": "x"})[0], 401)
        self.assertEqual(self.call("POST", "/api/v1/legacy-hook", {"k": "1"}, self.auth())[0], 201)

    def test_old_ticket_route_gone_when_not_registered(self):
        self.assertEqual(self.call("POST", "/webhook/tickets", {"ticket_id": "1"},
                                   self.auth())[0], 404)


class TestExpiredToken(ServerFixture, unittest.TestCase):
    overrides = {"token_ttl": -1}

    def test_expired_token_rejected(self):
        self.assertEqual(self.call("POST", "/webhook/tickets", SAMPLE, self.auth())[0], 401)


class TestSchemaMigration(unittest.TestCase):
    def test_new_fields_become_columns_without_losing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.db")
            conn = sqlite3.connect(path)
            conn.execute('CREATE TABLE "widgets" ("wid" TEXT PRIMARY KEY, "color" TEXT)')
            conn.execute("INSERT INTO widgets VALUES ('w1', 'red')")
            conn.commit()
            conn.close()
            resource = Resource("widgets", key="wid", fields={
                "wid": StringField(), "color": StringField(), "size": IntegerField()})
            repo = ResourceRepository(Database(path), resource)
            repo.create_table()
            cols = {r[1] for r in sqlite3.connect(path).execute('PRAGMA table_info("widgets")')}
            self.assertTrue({"size", "extra_fields", "raw_payload",
                             "received_at", "updated_at"} <= cols)
            self.assertEqual(repo.find("w1")["color"], "red")
            self.assertTrue(repo.save(resource.parse({"wid": "w2", "size": "3", "note": "hi"})))
            found = repo.find("w2")
            self.assertEqual((found["size"], found["extra_fields"]), (3, {"note": "hi"}))


class TestResourceRegistry(unittest.TestCase):
    def test_discovery_finds_tickets_and_skips_template(self):
        self.assertEqual([r.name for r in discover()], ["tickets"])

    def test_template_stays_valid(self):
        module = importlib.import_module("resources._template")
        self.assertEqual(module.RESOURCE.path, "/webhook/example_template")

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            ensure_unique([Resource("a"), Resource("b", path="/webhook/a")])

    def test_unsafe_names_rejected(self):
        with self.assertRaises(ValueError):
            Resource("bad-name")
        with self.assertRaises(ValueError):
            Resource("ok", fields={'x"; DROP TABLE tokens; --': StringField()})
        with self.assertRaises(ValueError):
            Resource("ok", fields={"raw_payload": StringField()})


class TestTokenTransports(ServerFixture, unittest.TestCase):
    """The CRM form only has an Authorization URL and an Access Token."""

    def test_get_with_credentials_in_url(self):
        code, body, headers = self.call("GET", "/auth/token?client_id=crm&client_secret=s3cret")
        self.assertEqual(code, 200)
        self.assertTrue(body["access_token"] == body["token"] == body["accessToken"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_get_without_credentials_is_401(self):
        self.assertEqual(self.call("GET", "/auth/token")[0], 401)
        self.assertEqual(self.call("GET", "/auth/token?client_id=crm&client_secret=bad")[0], 401)

    def test_post_with_empty_body_and_url_credentials(self):
        code, _, _ = self.call("POST", "/auth/token?client_id=crm&client_secret=s3cret", raw=b"")
        self.assertEqual(code, 200)

    def test_token_route_allows_get_and_post_only(self):
        code, _, headers = self.call("PUT", "/auth/token", raw=b"")
        self.assertEqual((code, headers["Allow"]), (405, "GET, POST"))

    def test_webhook_accepts_any_token_style(self):
        t = self.token()
        for headers in ({"Authorization": f"Bearer {t}"}, {"Authorization": f"bearer {t}"},
                        {"Authorization": f"Token {t}"}, {"Authorization": t},
                        {"X-Access-Token": t}):
            code, _, _ = self.call("POST", "/webhook/tickets", {"ticket_id": "H-1"}, headers)
            self.assertIn(code, (200, 201), headers)
        self.assertEqual(self.call("POST", "/webhook/tickets", {"ticket_id": "H-1"},
                                   {"Authorization": "Basic abc"})[0], 401)

    def test_query_string_on_webhook_url_is_ignored_for_routing(self):
        code, _, _ = self.call("POST", "/webhook/tickets?source=crm", {"ticket_id": "Q-1"},
                               self.auth())
        self.assertEqual(code, 201)

    def test_secrets_are_redacted_in_logs(self):
        from core.server import redact
        line = '"GET /auth/token?client_id=crm&client_secret=s3cret&x=1 HTTP/1.1" 200'
        self.assertNotIn("s3cret", redact(line))
        self.assertIn("client_id=crm", redact(line))


class TestStaticToken(ServerFixture, unittest.TestCase):
    overrides = {"static_token": "static-token-for-tests-0123456789"}

    def test_fixed_token_works_without_logging_in(self):
        h = {"Authorization": "Bearer static-token-for-tests-0123456789"}
        self.assertEqual(self.call("POST", "/webhook/tickets", {"ticket_id": "S-1"}, h)[0], 201)

    def test_wrong_fixed_token_rejected(self):
        h = {"Authorization": "Bearer static-token-for-tests-WRONG"}
        self.assertEqual(self.call("POST", "/webhook/tickets", {"ticket_id": "S-2"}, h)[0], 401)

    def test_dynamic_tokens_still_work(self):
        self.assertEqual(self.call("POST", "/webhook/tickets", {"ticket_id": "S-3"},
                                   self.auth())[0], 201)


if __name__ == "__main__":
    unittest.main()