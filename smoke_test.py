"""End-to-end check of your public URL: health, Authorization URL, webhook, auth enforcement.

Usage:  python smoke_test.py https://YOUR-DOMAIN.ngrok-free.dev
        python smoke_test.py            (tests http://127.0.0.1:<PORT> instead)

Reads CLIENT_ID / CLIENT_SECRET from .env. Secrets and full tokens are never printed.
Note: step 3 saves one ticket with ticket_id SMOKE-TEST (re-running just updates it).
"""
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from config import Config

TIMEOUT = float(os.environ.get("SMOKE_TIMEOUT", "15"))     # seconds to wait per request


def call(method, url, body=None, headers=None):
    """Return (status, text). status is None if the server could not be reached."""
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"ngrok-skip-browser-warning": "1", **(headers or {})}
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", "replace")
    except urllib.error.URLError as err:
        if isinstance(err.reason, TimeoutError):
            return None, f"no answer within {TIMEOUT:g}s"
        return None, str(err.reason)
    except TimeoutError:                                   # raised while waiting for the reply
        return None, f"no answer within {TIMEOUT:g}s"
    except (OSError, http.client.HTTPException) as err:    # dropped / reset / malformed reply
        return None, f"connection dropped: {err}"


def as_json(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def explain_failure(status, text, base):
    """Turn a failed /health response into a plain-English hint."""
    if status is None and text.startswith("no answer"):
        if "127.0.0.1" in base or "localhost" in base:
            return (f"{text}: the app accepted the connection but is stuck. Check the terminal "
                    "running `python app.py` (or `journalctl -u crm-webhook -n 30`) for errors.")
        return (f"{text}: the request got through to the internet but nothing answered. Run "
                "`python smoke_test.py` with NO URL to test the app locally. If that passes, the "
                "tunnel is the problem: restart ngrok and open http://127.0.0.1:4040 to see "
                "whether the request arrives. If the local test also hangs, the app is stuck.")
    if status is None and text.startswith("connection dropped"):
        return (f"{text}: the connection was cut before any reply. The app may have crashed or "
                "restarted, or the tunnel reconnected. Check the app's log, then try again.")
    if status is None:
        if "127.0.0.1" in base or "localhost" in base:
            return f"cannot connect ({text}): the app is not running. Start it with `python app.py`."
        return (f"cannot connect ({text}): check the URL is spelled exactly right "
                "and that you are online.")
    found = re.search(r"ERR_NGROK_\d+", text)
    code = found.group(0) if found else None
    if code == "ERR_NGROK_3200":
        return ("ngrok says this endpoint is offline (ERR_NGROK_3200): the ngrok agent is not "
                "running, or it is running with a different --url than this one. Start it with: "
                "ngrok http 8000 --url <this-url>")
    if code == "ERR_NGROK_8012":
        return ("ngrok is running but cannot reach your app (ERR_NGROK_8012): start "
                "`python app.py`, and make sure ngrok forwards to the port the app listens on "
                "(default 8000).")
    if code:
        return f"ngrok returned {code} (HTTP {status}): https://ngrok.com/docs/errors/{code.lower()}"
    return f"HTTP {status} from something that is not this app; got: {text[:120]!r}"


def main():
    cfg = Config.from_env()
    base = (sys.argv[1] if len(sys.argv) > 1 else f"http://127.0.0.1:{cfg.port}").rstrip("/")
    failures = 0

    def report(ok, label, hint=""):
        nonlocal failures
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            failures += 1
            if hint:
                print(f"       -> {hint}")

    print(f"Testing {base}\n")
    if cfg.uses_default_secret:
        print("WARNING: CLIENT_SECRET in .env is still the default.\n")

    # 1. Reachability
    status, text = call("GET", f"{base}/health")
    ok = status == 200 and (as_json(text) or {}).get("status") == "ok"
    report(ok, "1. GET /health", "" if ok else explain_failure(status, text, base))
    if not ok:
        return 1

    # 2. Authorization URL
    query = urllib.parse.urlencode({"client_id": cfg.client_id,
                                    "client_secret": cfg.client_secret})
    status, text = call("GET", f"{base}/auth/token?{query}")
    data = as_json(text) or {}
    token = data.get("access_token")
    report(status == 200 and bool(token), "2. GET /auth/token (credentials from .env)",
           text if status is None else
           "401 means the app is running with different credentials than .env now has. "
           "Restart `python app.py` after editing .env." if status == 401
           else f"unexpected response, HTTP {status}")
    if not token:
        return 1
    print(f"       token received: {token[:6]}... (expires_in={data.get('expires_in')}s)")

    # 3. Webhook with the token
    status, text = call("POST", f"{base}/webhook/tickets",
                        {"ticket_id": "SMOKE-TEST", "anything_else": "works"},
                        {"Authorization": f"Bearer {token}"})
    report(status in (200, 201), f"3. POST /webhook/tickets with token -> "
           + ("no reply" if status is None else f"HTTP {status}"), text[:200])

    # 4. Auth is actually enforced
    status, text = call("POST", f"{base}/webhook/tickets", {"ticket_id": "SMOKE-NOAUTH"})
    report(status == 401, "4. POST /webhook/tickets without token -> "
           + ("no reply" if status is None else f"HTTP {status} (expect 401)"),
           text if status is None else "the webhook accepted a request with no token!")

    print("\nAll checks passed." if not failures else f"\n{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())