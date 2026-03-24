import os
import logging
from typing import Optional
from dotenv import load_dotenv

# ---------------- ENV ---------------- #

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set — see .env.example")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set — see .env.example")

# ---------------- MODEL SETTINGS ---------------- #

MODEL_NAME = "llama-3.3-70b-versatile"
MAX_TOKENS = 4096
TEMPERATURE = 0.6

SYSTEM_PROMPT = (
    "You are CalmNest, a calm, warm, and supportive mental wellbeing assistant. "
    "You listen without judgment. "
    "You do NOT give medical advice or diagnoses. "
    "Keep responses gentle, empathetic, and concise."
)

# ---------------- CHECKIN SETTINGS ---------------- #

# Time slot boundaries (24h format, server local time)
CHECKIN_SLOTS = {
    "morning":   (6, 12),   # 06:00 – 11:59
    "afternoon": (12, 17),  # 12:00 – 16:59
    "evening":   (17, 21),  # 17:00 – 20:59
    "night":     (21, 6),   # 21:00 – 05:59 (wraps around)
}

CHECKIN_MESSAGES = {
    "morning":   "Good morning 🌅 How are you feeling today?",
    "afternoon": "Hey there 🌤️ Just checking in — how's your afternoon going?",
    "evening":   "Good evening 🌆 How was your day? I'm here if you want to talk.",
    "night":     "Hey 🌙 Winding down? Remember, it's okay to rest. I'm here if you need me.",
}

# Rate limiting
RATE_LIMIT = "120/minute"

# ---------------- LOGGING ---------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("calmnest")

# Avoid printing full request URLs (can include sensitive tokens in some SDK calls).
logging.getLogger("httpx").setLevel(logging.WARNING)


def _default_db_path() -> str:
    """Choose a persistent SQLite path when running on Azure App Service."""
    if os.getenv("WEBSITE_INSTANCE_ID") or os.getenv("WEBSITE_SITE_NAME"):
        return "/home/site/calmnest.db"
    return "calmnest.db"


# Database
DB_PATH = os.getenv("CALMNEST_DB_PATH") or _default_db_path()


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    """Parse common env var booleans."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Optional Supermemory integration
SUPERMEMORY_ENABLED = _as_bool(os.getenv("ENABLE_SUPERMEMORY"), default=False)
SUPERMEMORY_API_KEY = os.getenv("SUPERMEMORY_API_KEY", "").strip()
SUPERMEMORY_BASE_URL = os.getenv("SUPERMEMORY_BASE_URL", "https://api.supermemory.ai").rstrip("/")
SUPERMEMORY_TIMEOUT_MS = int(os.getenv("SUPERMEMORY_TIMEOUT_MS", "2500"))
SUPERMEMORY_SEARCH_LIMIT = int(os.getenv("SUPERMEMORY_SEARCH_LIMIT", "6"))

if SUPERMEMORY_ENABLED and not SUPERMEMORY_API_KEY:
    logger.warning(
        "ENABLE_SUPERMEMORY is true but SUPERMEMORY_API_KEY is missing; "
        "Supermemory integration is disabled."
    )
    SUPERMEMORY_ENABLED = False
