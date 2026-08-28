import os
from pathlib import Path
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

_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
DATA_DIR = _volume or os.getenv("DATA_DIR", "/app/data").strip() or "/app/data"
_raw_db_path = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"
DB_PATH = _raw_db_path if os.path.isabs(_raw_db_path) else str(Path(DATA_DIR) / _raw_db_path)
BACKUP_DIR = os.getenv("BACKUP_DIR", "").strip() or str(Path(DB_PATH).parent / "backups")

ADMIN_MINIAPP_URL = os.getenv("ADMIN_MINIAPP_URL", "").strip()
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"

# AI defaults can be changed from Mini App without changing code.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant").strip()
