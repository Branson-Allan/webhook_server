"""Prints the two strings the CRM's authorization form asks for.

Usage:  python connection_info.py https://YOUR-DOMAIN.ngrok-free.app
Reads CLIENT_ID / CLIENT_SECRET / STATIC_ACCESS_TOKEN from .env.
"""
import sys
from urllib.parse import quote

from config import Config


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else "https://YOUR-DOMAIN.ngrok-free.app").rstrip("/")
    cfg = Config.from_env()
    auth_url = (f"{base}/auth/token?client_id={quote(cfg.client_id, safe='')}"
                f"&client_secret={quote(cfg.client_secret, safe='')}")

    print("\n== OPTION 1: the CRM fetches a fresh token itself (Dynamic) ==")
    print(f"Authorization URL : {auth_url}")
    print("Access Token      : access_token")
    print("   (the name of the field in the response that holds the token;")
    print("    'token' and 'accessToken' also work)")

    print("\n== OPTION 2: the CRM wants a fixed token pasted in ==")
    if cfg.static_token:
        print(f"Authorization URL : {auth_url}")
        print(f"Access Token      : {cfg.static_token}")
    else:
        print("STATIC_ACCESS_TOKEN is not set in .env. Generate one with:")
        print('   python -c "import secrets; print(secrets.token_urlsafe(32))"')
        print("then add  STATIC_ACCESS_TOKEN=<value>  to .env and restart the app.")

    print(f"\nWebhook URL       : {base}/webhook/tickets")
    if cfg.uses_default_secret:
        print("\nWARNING: CLIENT_SECRET is still the default. Set your own in .env first.")
    print("\nTreat the Authorization URL as a secret: it contains your client secret.\n")


if __name__ == "__main__":
    main()