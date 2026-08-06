import os
import google.generativeai as genai


genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)


model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


async def analyze_story(story: str):

    prompt = f"""
Ты помощник Telegram-канала "Проблем нет".

Проанализируй историю человека бережно.

Создай ответ в формате:

💭 Суть проблемы:
(кратко опиши ситуацию)

🧠 Возможные причины:
(почему это может происходить)

🌱 Что можно попробовать:
(практические советы)

💙 Поддержка:
(тёплое сообщение человеку)

Не ставь диагнозы.
Не заменяй психолога.
Пиши понятно и человечно.

История человека:

{story}
"""

    response = await model.generate_content_async(prompt)

    return response.text
