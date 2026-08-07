import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ADMIN_IDS = [
    int(admin_id.strip())
    for admin_id in os.getenv("ADMIN_IDS", "").split(",")
    if admin_id.strip()
]

CHANNEL_ID = os.getenv("CHANNEL_ID")

DB_PATH = os.getenv(
    "DB_PATH",
    "stories.db"
)


if not BOT_TOKEN:
    raise ValueError(
        "Не найден BOT_TOKEN в .env"
    )


if not ADMIN_IDS:
    raise ValueError(
        "Не найден ADMIN_IDS в .env"
    )


if not CHANNEL_ID:
    raise ValueError(
        "Не найден CHANNEL_ID в .env"
    )
