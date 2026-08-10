import os

from dotenv import load_dotenv
from groq import AsyncGroq


load_dotenv()


def _client() -> AsyncGroq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Не задан GROQ_API_KEY")
    return AsyncGroq(api_key=api_key)


async def analyze_story(story: str):
    response = await _client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """
Ты помощник Telegram-канала "Проблем нет".

Анализируй истории людей бережно.

Формат:

💭 Суть проблемы:
кратко

🧠 Возможные причины:
объяснение

🌱 Что можно попробовать:
практические советы

💙 Поддержка:
тёплое сообщение

Не ставь диагнозы.
Не заменяй психолога.
Пиши понятно и человечно.
""",
            },
            {"role": "user", "content": story},
        ],
    )
    return response.choices[0].message.content
