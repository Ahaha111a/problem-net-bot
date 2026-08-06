import os
from groq import AsyncGroq


client = AsyncGroq(
    api_key=os.getenv("GROQ_API_KEY")
)


async def create_post(story: str):

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """
Ты редактор Telegram-канала "Проблем нет".

Преврати историю человека в красивый анонимный пост.

Правила:
- не раскрывай личность;
- не используй слово "пациент";
- не ставь диагнозы;
- пиши тепло и поддерживающе.

Структура:

📌 История подписчика

💭 Ситуация:

🧠 Разбор:

🌱 Что можно попробовать:

💙 Поддержка:
"""
            },
            {
                "role": "user",
                "content": story
            }
        ]
    )

    return response.choices[0].message.content
