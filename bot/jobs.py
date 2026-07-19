"""Background jobs: metrics snapshots and price-alert polling."""

from __future__ import annotations

import asyncio
import json

from telegram.ext import ContextTypes

from bot.config import logger
from bot.metrics import snapshot
from bot.services import _format_price, _get_yfinance_info
from bot.storage import alert_delete_by_id, alerts_all
from bot.symbols import is_crypto_symbol


async def log_metrics_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = snapshot()
    logger.info(f"metrics_snapshot {json.dumps(data, sort_keys=True)}")


async def check_price_alerts_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = alerts_all()
    if not rows:
        return

    by_symbol: dict[str, list[dict]] = {}
    for row in rows:
        by_symbol.setdefault(row["symbol"], []).append(row)

    symbols = list(by_symbol.keys())
    results = await asyncio.gather(
        *[_get_yfinance_info(symbol) for symbol in symbols],
        return_exceptions=True,
    )

    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            logger.error(f"Alert poll failed for {symbol}: {result}")
            continue

        info = result
        if not info:
            continue

        price = info.get("lastPrice") or info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            continue

        for alert in by_symbol[symbol]:
            direction = alert["direction"]
            threshold = float(alert["threshold"])
            fired = (direction == "above" and price >= threshold) or (direction == "below" and price <= threshold)
            if not fired:
                continue

            price_str = _format_price(price, is_crypto_symbol(symbol))
            text = f"🔔 <b>Alert #{alert['id']}</b>\n{symbol} is {price_str} ({direction} {threshold})"
            try:
                await context.bot.send_message(chat_id=alert["chat_id"], text=text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send alert #{alert['id']}: {e}")
            alert_delete_by_id(alert["id"])
