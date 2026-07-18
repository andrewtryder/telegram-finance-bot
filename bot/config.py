import logging
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Log level config
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("bot")
logging.getLogger("httpx").setLevel(logging.WARNING)

# Constants
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")
HONEYBADGER_API_KEY = os.getenv("HONEYBADGER_API_KEY")
HONEYBADGER_ENVIRONMENT = os.getenv("HONEYBADGER_ENVIRONMENT") or os.getenv("RAILWAY_ENVIRONMENT") or "development"
PROVIDER_TIMEOUT = float(os.getenv("PROVIDER_TIMEOUT", "10.0"))
INITIAL_BACKOFF = float(os.getenv("INITIAL_BACKOFF", "0.5"))
MAX_SEARCH_LEN = 64

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
