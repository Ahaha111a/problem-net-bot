import os
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задана переменная окружения {name}")
    return value


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MODERATOR_BOT_TOKEN = os.getenv("MODERATOR_BOT_TOKEN", "").strip()
if not BOT_TOKEN and not MODERATOR_BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN или MODERATOR_BOT_TOKEN.")

ADMIN_IDS = [
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_IDS", "").split(",")
    if user_id.strip()
]
# ADMIN_IDS is required only for moderator authorization; the user bot can run without it.

CHANNEL_ID = _required("CHANNEL_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip().lstrip("@")
try:
    CHANNEL_FIRST_MESSAGE_ID = max(1, int(os.getenv("CHANNEL_FIRST_MESSAGE_ID", "1")))
except (TypeError, ValueError):
    CHANNEL_FIRST_MESSAGE_ID = 1
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").strip().lstrip("@").strip()
try:
    CHANNEL_FIRST_MESSAGE_ID = max(1, int(os.getenv("CHANNEL_FIRST_MESSAGE_ID", "1")))
except (TypeError, ValueError):
    CHANNEL_FIRST_MESSAGE_ID = 1

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
AI_QUEUE_ENABLED = os.getenv("AI_QUEUE_ENABLED", "1").strip() == "1"
AI_EMERGENCY_DIRECT = os.getenv("AI_EMERGENCY_DIRECT", "1").strip() == "1"
BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/backups").strip() or "/app/backups"

_railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
ADMIN_MINIAPP_URL = os.getenv("ADMIN_MINIAPP_URL", "").strip().rstrip("/")
if not ADMIN_MINIAPP_URL and _railway_public_domain:
    ADMIN_MINIAPP_URL = f"https://{_railway_public_domain}/admin"
_mini_base = ADMIN_MINIAPP_URL.rstrip("/")
if _mini_base.endswith("/admin"):
    _mini_base = _mini_base[:-6]
FOUNDER_URL = os.getenv("FOUNDER_URL", (_mini_base + "/founder") if _mini_base else "").strip().rstrip("/")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"

# AI defaults can be changed from Mini App without changing code.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b").strip()
GROQ_SAFETY_MODEL = os.getenv("GROQ_SAFETY_MODEL", "").strip()
GROQ_MODELS = [
    x.strip()
    for x in os.getenv(
        "GROQ_MODELS",
        f"{GROQ_MODEL},{GROQ_FALLBACK_MODEL},qwen/qwen3.6-27b",
    ).split(",")
    if x.strip()
]
