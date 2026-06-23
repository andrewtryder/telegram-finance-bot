import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging (Set to INFO, but we manually log all critical actions)
# If you want to see deep library debug data, change logging.INFO to logging.DEBUG
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("bot")

# Constants
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

INDEX_MAPPING = {
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones",
    "^IXIC": "Nasdaq"
}
