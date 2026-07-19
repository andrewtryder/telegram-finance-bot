"""In-memory usage metrics for periodic logging."""

from __future__ import annotations

import html
import threading
from collections import defaultdict

_lock = threading.Lock()
_commands_total: dict[str, int] = defaultdict(int)
_errors_total = 0
_provider_errors: dict[str, int] = defaultdict(int)


def record_command(name: str) -> None:
    with _lock:
        _commands_total[name] += 1


def record_error() -> None:
    with _lock:
        global _errors_total
        _errors_total += 1


def record_provider_error(provider: str) -> None:
    with _lock:
        _provider_errors[provider] += 1


def snapshot() -> dict:
    with _lock:
        return {
            "commands_total": dict(_commands_total),
            "errors_total": _errors_total,
            "provider_errors": dict(_provider_errors),
        }


def format_stats_html(data: dict | None = None) -> str:
    """HTML summary of in-memory metrics for /admin stats."""
    data = data if data is not None else snapshot()
    lines = ["📊 <b>Admin stats</b>", "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", ""]

    commands = data.get("commands_total") or {}
    lines.append("<b>Commands</b>")
    if commands:
        for name in sorted(commands):
            lines.append(f"  {html.escape(str(name))}: {commands[name]}")
    else:
        lines.append("  (none yet)")

    lines.append("")
    lines.append(f"<b>Errors:</b> {data.get('errors_total', 0)}")

    providers = data.get("provider_errors") or {}
    lines.append("<b>Provider errors</b>")
    if providers:
        for name in sorted(providers):
            lines.append(f"  {html.escape(str(name))}: {providers[name]}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def reset() -> None:
    """Test helper."""
    with _lock:
        global _errors_total
        _commands_total.clear()
        _errors_total = 0
        _provider_errors.clear()
