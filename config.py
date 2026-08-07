import os
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env

class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    DB_PATH: str = "stories.db"
    CHANNEL_ID: int = int(os.getenv("CHANNEL_ID", 0))  # ID канала для публикаций (положи туда свой)
    ADMIN_IDS: list[int] = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

config = Config()
