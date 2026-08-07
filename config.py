import os
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env

class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    DB_PATH: str = "stories.db"
    CHANNEL_ID: int = 0
    ADMIN_IDS: list[int] = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

config = Config()
