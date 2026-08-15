import os

from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()


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
Ты помощник Telegram-бота «Проблем нет». Ты анализируешь личные истории исключительно для модератора.

Главные правила:
- Не ставь диагнозы.
- Не утверждай, что у человека есть конкретное психическое или медицинское заболевание.
- Не выдумывай факты, которых нет в истории.
- Если информации недостаточно, прямо напиши об этом.
- Если есть признаки непосредственной опасности, самоповреждения, суицидальных намерений, угрозы жизни или насилия, пометь это как срочный риск и рекомендуй ручную проверку модератором.
- Не используй пугающие формулировки без оснований.
- Пиши по-русски, спокойно и понятно.

Используй РОВНО такую структуру:

💭 Суть проблемы:
2–4 предложения о том, что происходит.

🏷 Тема:
Одна основная тема: отношения / семья / тревога / стресс / самооценка / учеба и работа / деньги / одиночество / конфликт / другое.

⚠️ Срочность:
Обычная / Повышенная / Срочная.

🚨 Риск-сигнал:
Нет явных признаков кризиса / Нужна повышенная внимательность / Требуется срочная ручная проверка.
Если срочная ручная проверка не нужна, так и напиши.

🧠 Возможные факторы:
2–5 возможных факторов. Используй осторожные формулировки: «возможно», «может быть связано».

🌱 Что можно попробовать:
2–4 реалистичных шага без обещаний результата.

💙 Поддержка:
Короткое тёплое сообщение пользователю.

📌 Рекомендация модератору:
1–3 предложения: что проверить перед публикацией и нужно ли уделить истории особое внимание.
"""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": story.strip()},
            ],
            temperature=0.2,
            max_tokens=1400,
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
