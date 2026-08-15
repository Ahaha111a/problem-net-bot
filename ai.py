import os

from dotenv import load_dotenv
from groq import AsyncGroq


load_dotenv()

MODEL = "llama-3.3-70b-versatile"


def get_groq_client() -> AsyncGroq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY не задан. Добавьте GROQ_API_KEY в переменные окружения Railway."
        )

    return AsyncGroq(api_key=api_key)


async def analyze_story(story: str) -> str:
    if not story or not story.strip():
        raise ValueError("История для анализа пустая.")

    client = get_groq_client()

    system_prompt = """
Ты помощник Telegram-бота «Проблем нет».

Твоя задача — бережно анализировать пользовательские истории для модератора.
Не ставь диагнозы и не утверждай, что у человека есть конкретное заболевание.

Используй РОВНО такую структуру:

💭 Суть проблемы:
Краткое описание основной ситуации.

🏷 Тема:
Выбери одну основную тему: отношения, семья, тревога, стресс, самооценка, учеба/работа, деньги, одиночество, конфликт, другое.

⚠️ Срочность:
Обычная / Повышенная / Срочная.
Срочная — только если в тексте есть признаки непосредственной опасности, самоповреждения, суицидальных намерений, угрозы жизни или другого кризиса. Не ставь диагноз.

🧠 Возможные факторы:
Несколько возможных факторов, которые могут влиять на ситуацию. Используй формулировки «возможно», «может быть связано».

🌱 Что можно попробовать:
2–4 простых и реалистичных шага.

💙 Поддержка:
Короткое теплое сообщение.

📌 Рекомендация модератору:
Коротко укажи, стоит ли обратить особое внимание на историю.

Если срочность «Срочная», обязательно укажи, что модератору следует проверить ситуацию вручную как можно скорее.

Пиши по-русски, спокойно, без осуждения и сложной терминологии.
"""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": story.strip()},
            ],
            temperature=0.3,
            max_tokens=1200,
        )

        if not response.choices:
            raise RuntimeError("Groq вернул ответ без choices.")

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Groq вернул пустой текст.")

        return content.strip()

    except Exception as error:
        print("================ GROQ ERROR ================")
        print(f"Тип ошибки: {type(error).__name__}")
        print(f"Ошибка: {error}")
        print("=============================================")
        raise
