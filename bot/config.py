import json
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for Railway-friendly structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> logging.Logger:
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_format_env = os.getenv("LOG_FORMAT", "").lower().strip()
    use_json = log_format_env == "json" or (not log_format_env and bool(os.getenv("RAILWAY_ENVIRONMENT")))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger("bot")


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = _configure_logging()

# Constants
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HONEYBADGER_API_KEY = os.getenv("HONEYBADGER_API_KEY")
HONEYBADGER_ENVIRONMENT = os.getenv("HONEYBADGER_ENVIRONMENT") or os.getenv("RAILWAY_ENVIRONMENT") or "development"
PROVIDER_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT", "10.0"))
INITIAL_BACKOFF = float(os.getenv("INITIAL_BACKOFF", "0.5"))
MAX_SEARCH_LEN = 64
DATA_DIR = os.getenv("DATA_DIR", "./data")

# Parse ALLOWED_CHAT_IDS
ALLOWED_CHAT_IDS = set()
ALLOWED_CHAT_IDS_ENV = os.getenv("ALLOWED_CHAT_IDS")
if ALLOWED_CHAT_IDS_ENV:
    for cid in ALLOWED_CHAT_IDS_ENV.split(","):
        cid = cid.strip().strip("'\"")
        if cid:
            try:
                ALLOWED_CHAT_IDS.add(int(cid))
            except ValueError:
                logger.warning(f"Invalid chat ID in ALLOWED_CHAT_IDS: {cid}")

# Owner user IDs for /admin (separate from chat allowlist)
ADMIN_USER_IDS = set()
ADMIN_USER_IDS_ENV = os.getenv("ADMIN_USER_IDS")
if ADMIN_USER_IDS_ENV:
    for uid in ADMIN_USER_IDS_ENV.split(","):
        uid = uid.strip().strip("'\"")
        if uid:
            try:
                ADMIN_USER_IDS.add(int(uid))
            except ValueError:
                logger.warning(f"Invalid user ID in ADMIN_USER_IDS: {uid}")

INDEX_MAPPING = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq"}


def init_honeybadger() -> bool:
    """Configure Honeybadger when an API key is present. Returns True if enabled."""
    if not HONEYBADGER_API_KEY:
        logger.info("HONEYBADGER_API_KEY not set; error reporting disabled.")
        return False

    from honeybadger import honeybadger

    honeybadger.configure(
        api_key=HONEYBADGER_API_KEY,
        environment=HONEYBADGER_ENVIRONMENT,
    )
    logger.info(f"Honeybadger enabled (environment={HONEYBADGER_ENVIRONMENT}).")
    return True


def notify_honeybadger(error: BaseException | None, **context) -> None:
    """Report an exception to Honeybadger when configured."""
    if not HONEYBADGER_API_KEY or error is None:
        return

    try:
        from honeybadger import honeybadger

        honeybadger.notify(error, context=context or None)
    except Exception as e:
        logger.error(f"Failed to notify Honeybadger: {e}")
