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

ADMIN_IDS = [
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_IDS", "").split(",")
    if user_id.strip()
]

if not ADMIN_IDS:
    raise RuntimeError("Не задан ADMIN_IDS. Укажите Telegram ID через запятую.")

CHANNEL_ID = _required("CHANNEL_ID")

# Railway: если DB_PATH задан относительным путём (например bot.db),
# автоматически помещаем БД в persistent volume. Это предотвращает
# сброс статистики при каждом redeploy.
_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
_default_data_dir = _volume or os.getenv("DATA_DIR", "/app/data").strip() or "/app/data"
_raw_db_path = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"

if os.path.isabs(_raw_db_path):
    DB_PATH = _raw_db_path
else:
    DB_PATH = str(Path(_default_data_dir) / _raw_db_path)

BACKUP_DIR = os.getenv("BACKUP_DIR", "").strip() or str(Path(DB_PATH).parent / "backups")

# Необязательный токен второго бота-модератора. Пока не задан —
# основной бот продолжает работать в текущем режиме.
MODERATOR_BOT_TOKEN = os.getenv("MODERATOR_BOT_TOKEN", "").strip()
