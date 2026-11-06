"""Python HTTP webhook transport for local and Railway deployments."""

import asyncio
import hmac
import os
import re
from collections import OrderedDict

from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder

from bot.config import BOT_MODE, TELEGRAM_BOT_TOKEN, init_honeybadger, validate_config
from bot.main import register_handlers


def create_server(application, secret: str) -> web.Application:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
        raise ValueError("A valid TELEGRAM_WEBHOOK_SECRET is required.")
    server = web.Application(client_max_size=1024 * 1024)
    seen: OrderedDict[int, None] = OrderedDict()
    lock = asyncio.Lock()

    async def health(_request):
        return web.json_response({"ok": True})

    async def webhook(request):
        actual = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(actual.encode(), secret.encode()):
            raise web.HTTPForbidden()
        try:
            payload = await request.json()
            update_id = payload["update_id"]
            if isinstance(update_id, bool) or not isinstance(update_id, int) or update_id < 0:
                raise ValueError("Invalid update ID")
        except (ValueError, KeyError, TypeError):
            raise web.HTTPBadRequest() from None
        async with lock:
            if update_id in seen:
                return web.json_response({"ok": True, "duplicate": True})
            try:
                update = Update.de_json(payload, application.bot)
                await application.process_update(update)
            except Exception:
                raise web.HTTPServiceUnavailable() from None
            seen[update_id] = None
            if len(seen) > 10000:
                seen.popitem(last=False)
        return web.json_response({"ok": True})

    server.router.add_get("/health", health)
    server.router.add_post("/webhook", webhook)
    return server


def main():
    validate_config()
    if BOT_MODE != "webhook":
        raise RuntimeError("bot.webhook requires BOT_MODE=webhook.")
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    init_honeybadger()
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(application)
    server = create_server(application, os.getenv("TELEGRAM_WEBHOOK_SECRET", ""))

    async def startup(_server):
        await application.initialize()
        await application.start()

    async def cleanup(_server):
        await application.stop()
        await application.shutdown()

    server.on_startup.append(startup)
    server.on_cleanup.append(cleanup)
    web.run_app(server, host="0.0.0.0", port=int(os.getenv("PORT", "8080")), access_log=None)


if __name__ == "__main__":
    main()
