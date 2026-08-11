import os

from dotenv import load_dotenv
from groq import AsyncGroq


load_dotenv()


MODEL = "llama-3.3-70b-versatile"


def get_groq_client() -> AsyncGroq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY не задан. "
            "Добавьте GROQ_API_KEY в переменные окружения."
        )

    return AsyncGroq(
        api_key=api_key,
    )


async def analyze_story(story: str) -> str:
    """
    Анализирует историю пользователя через Groq.
    """

    if not story or not story.strip():
        raise ValueError("История для анализа пустая.")

    client = get_groq_client()

    system_prompt = """
Ты помощник Telegram-бота «Проблем нет».

Твоя задача — бережно и понятно анализировать истории людей.

Для каждой истории используй следующий формат:

💭 Суть проблемы:
Кратко опиши, в чём основная проблема человека.

🧠 Возможные причины:
Укажи возможные причины и факторы, которые могут влиять на ситуацию.
Не ставь медицинских или психологических диагнозов.

🌱 Что можно попробовать:
Предложи несколько простых и реалистичных действий, которые человек может попробовать.

💙 Поддержка:
Напиши короткое тёплое сообщение поддержки.

Правила:
- Не ставь диагнозы.
- Не утверждай, что у человека есть конкретное заболевание.
- Не заменяй психолога или врача.
- Не осуждай человека.
- Не используй слишком сложные термины.
- Пиши на русском языке.
- Отвечай понятно, спокойно и человечно.
- Не добавляй лишние разделы.
"""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": story.strip(),
                },
            ],
            temperature=0.4,
            max_tokens=1000,
        )

        if not response.choices:
            raise RuntimeError(
                "Groq вернул ответ без choices."
            )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "Groq вернул пустой текст."
            )

        return content.strip()

    except Exception as error:
        print(
            "================ GROQ ERROR ================"
        )
        print(
            f"Тип ошибки: {type(error).__name__}"
        )
        print(
            f"Ошибка: {error}"
        )
        print(
            "============================================="
        )

        raise
