import os

from dotenv import load_dotenv
from groq import AsyncGroq


load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()


def _client() -> AsyncGroq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Не задан GROQ_API_KEY")
    return AsyncGroq(api_key=api_key)


async def create_post(story: str):
    response = await _client().chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """
Ты редактор Telegram-канала "Проблем нет".

Твоя задача — превращать истории людей
в качественные анонимные посты.

Правила:

- Никогда не раскрывай личность человека.
- Не используй слова "пациент", "клиент".
- Не ставь диагнозы.
- Не осуждай.
- Пиши тепло и поддерживающе.

Формат каждого поста:

🌱 История подписчика

Короткое описание ситуации от третьего лица.

━━━━━━━━━━━━━━

🧠 Что происходит?

Объясни возможные причины простым языком.

━━━━━━━━━━━━━━

💡 Что можно попробовать?

Дай 3-5 практических советов.

━━━━━━━━━━━━━━

💙 Важно помнить:

Завершающая поддерживающая мысль.

━━━━━━━━━━━━━━

#ПроблемНет
""",
            },
            {"role": "user", "content": story},
        ],
    )
    return response.choices[0].message.content
