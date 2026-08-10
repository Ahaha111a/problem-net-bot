import os

from dotenv import load_dotenv


load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}"
        )
    return value


BOT_TOKEN = _required("BOT_TOKEN")

ADMIN_IDS = [
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_IDS", "").split(",")
    if user_id.strip()
]

if not ADMIN_IDS:
    raise RuntimeError(
        "Не задан ADMIN_IDS. Укажите один или несколько Telegram ID через запятую."
    )

# Числовой ID канала (-100...) или @username публичного канала.
CHANNEL_ID = _required("CHANNEL_ID")

DB_PATH = (
    os.getenv("DB_PATH", "bot.db").strip()
    or "bot.db"
)
