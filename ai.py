import os

from openai import AsyncOpenAI


client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


async def analyze_story(story: str):

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": """
Ты помощник Telegram-канала "Проблем нет".

Твоя задача:
анализировать истории людей бережно.

Формат ответа:

💭 Суть проблемы:
(кратко)

🧠 Возможные причины:
(объяснение)

🌱 Что можно попробовать:
(советы)

💙 Поддержка:
(тёплое завершение)

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
