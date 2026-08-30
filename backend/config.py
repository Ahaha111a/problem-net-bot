import os
from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задана переменная окружения {name}")
    return value


BOT_TOKEN = _required("BOT_TOKEN")
MODERATOR_BOT_TOKEN = os.getenv("MODERATOR_BOT_TOKEN", "").strip()

ADMIN_IDS = [
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_IDS", "").split(",")
    if user_id.strip()
]
if not ADMIN_IDS:
    raise RuntimeError("Не задан ADMIN_IDS. Укажите Telegram ID через запятую.")

CHANNEL_ID = _required("CHANNEL_ID")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "").strip()
AI_QUEUE_ENABLED = os.getenv("AI_QUEUE_ENABLED", "1").strip() == "1"
AI_EMERGENCY_DIRECT = os.getenv("AI_EMERGENCY_DIRECT", "1").strip() == "1"
BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/backups").strip() or "/app/backups"

ADMIN_MINIAPP_URL = os.getenv("ADMIN_MINIAPP_URL", "").strip()
_mini_base = ADMIN_MINIAPP_URL.rstrip("/")
if _mini_base.endswith("/admin"):
    _mini_base = _mini_base[:-6]
FOUNDER_URL = os.getenv("FOUNDER_URL", (_mini_base + "/founder") if _mini_base else "").strip()
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"

# AI defaults can be changed from Mini App without changing code.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant").strip()
