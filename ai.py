import os
from groq import AsyncGroq


client = AsyncGroq(
    api_key=os.getenv("GROQ_API_KEY")
)


async def analyze_story(story: str):

    response = await client.chat.completions.create(
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
"""
            },
            {
                "role": "user",
                "content": story
            }
        ]
    )

    return response.choices[0].message.content
