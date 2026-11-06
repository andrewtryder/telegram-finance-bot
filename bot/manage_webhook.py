"""Register, remove or inspect a Telegram webhook without exposing the token."""

import argparse
import json
import os
import re
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


def run(action: str, environ=None, client=httpx) -> dict:
    environ = os.environ if environ is None else environ
    token = environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required.")
    if action == "register":
        url = environ.get("WEBHOOK_URL", "")
        secret = environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
            raise ValueError("An HTTPS WEBHOOK_URL and valid TELEGRAM_WEBHOOK_SECRET are required.")
        method = "setWebhook"
        data = {"url": url, "secret_token": secret, "drop_pending_updates": False}
    elif action == "remove":
        method = "deleteWebhook"
        data = {"drop_pending_updates": False}
    elif action == "info":
        method = "getWebhookInfo"
        data = {}
    else:
        raise ValueError("Choose register, remove, or info.")

    try:
        response = client.post(f"https://api.telegram.org/bot{token}/{method}", json=data, timeout=15)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise ValueError("Telegram rejected the request.")
        return result
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(
            "Telegram webhook operation failed. Check credentials, URL and Telegram availability."
        ) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "remove", "info"))
    args = parser.parse_args()
    load_dotenv()
    try:
        result = run(args.action)
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
    if args.action == "info":
        print(json.dumps(result.get("result")))
    else:
        print(f"Webhook {'registered' if args.action == 'register' else 'removed'}.")


if __name__ == "__main__":
    main()
