import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import AsyncGroq


load_dotenv()


# =========================================================
# GROQ CONFIG
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile",
).strip()


if not GROQ_API_KEY:
    print(
        "⚠️ GROQ_API_KEY не задан. "
        "ИИ-функции будут недоступны."
    )


client = (
    AsyncGroq(
        api_key=GROQ_API_KEY,
    )
    if GROQ_API_KEY
    else None
)


# =========================================================
# COMMON GROQ REQUEST
# =========================================================

async def _ask_groq(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:

    if client is None:
        raise RuntimeError(
            "GROQ_API_KEY не задан в переменных окружения."
        )

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.choices:
            raise RuntimeError(
                "Groq не вернул ни одного варианта ответа."
            )

        result = response.choices[0].message.content

        if not result:
            raise RuntimeError(
                "Groq вернул пустой ответ."
            )

        return result.strip()

    except Exception as error:
        print(
            "\n================ GROQ ERROR ================"
        )
        print(
            f"Тип ошибки: {type(error).__name__}"
        )
        print(
            f"Ошибка: {error}"
        )
        print(
            "============================================\n"
        )

        raise


# =========================================================
# STORY ANALYSIS
# =========================================================

async def analyze_story(story: str) -> str:

    system_prompt = """
Ты — ИИ-помощник проекта «Проблем нет».

Твоя задача — внимательно и бережно анализировать
истории пользователей.

Не ставь медицинских диагнозов.

Не утверждай, что точно знаешь психологическое состояние
человека.

Не используй осуждающие формулировки.

Ответ должен быть понятным для администратора,
который будет модерировать историю.

Верни анализ в следующем формате:

🏷 Тема:
<одна короткая тема>

💭 Основная проблема:
<краткое описание>

🧠 Эмоциональное состояние:
<осторожное описание без диагноза>

⚠️ На что обратить внимание:
<важные моменты>

💡 Возможное направление поддержки:
<что можно предложить пользователю>

📌 Рекомендация:
<короткая рекомендация для администратора>
"""

    user_prompt = f"""
Проанализируй следующую историю пользователя.

ИСТОРИЯ:

{story}
"""

    return await _ask_groq(
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.25,
        max_tokens=1800,
    )


# =========================================================
# AI MODERATION
# =========================================================

async def moderate_story(
    story: str,
    post_text: str = "",
) -> str:

    system_prompt = """
Ты — система предварительной ИИ-модерации
анонимного Telegram-проекта.

Проведи дополнительную проверку истории
перед публикацией.

ВАЖНО:

Ты НЕ принимаешь окончательное решение.
Окончательное решение принимает человек-модератор.

Проверь:

1. Самоповреждение или суицидальные признаки.
2. Угрозы или насилие.
3. Опасные инструкции.
4. Персональные данные.
5. Возможность идентификации человека.
6. Чувствительные данные.
7. Оскорбительный или дискриминационный контент.
8. Соответствие готового поста исходной истории.
9. Не содержит ли готовый пост информацию,
   которой не было в исходной истории.
10. Общую безопасность публикации.

Верни ответ строго в формате:

🛡 ИИ-МОДЕРАЦИЯ

🚨 Риск:
<низкий / средний / высокий / критический>

🔐 Персональные данные:
<нет / возможно / обнаружены>

⚠️ Потенциально опасный контент:
<нет / есть>

👤 Возможность идентификации:
<низкая / средняя / высокая>

📝 Качество поста:
<хорошее / требует проверки / плохое>

🔎 Проблемы:
<список проблем или "не обнаружены">

📌 РЕКОМЕНДАЦИЯ:
<ПУБЛИКОВАТЬ / ПРОВЕРИТЬ ВРУЧНУЮ / НЕ ПУБЛИКОВАТЬ>

Объяснение:
<краткое объяснение решения>
"""

    user_prompt = f"""
ИСХОДНАЯ ИСТОРИЯ:

{story}


ГОТОВЫЙ ПОСТ:

{post_text if post_text else "Пост отсутствует."}
"""

    return await _ask_groq(
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.1,
        max_tokens=1800,
    )


# =========================================================
# AI QUALITY CHECK
# =========================================================

async def check_story_quality(
    story: str,
    post_text: str = "",
) -> str:

    system_prompt = """
Ты — редактор анонимного Telegram-проекта.

Проверь качество подготовленного поста.

Нужно определить:

- сохранился ли смысл истории;
- не придумал ли ИИ новые факты;
- не потеряны ли важные детали;
- нет ли чрезмерной драматизации;
- нет ли раскрытия личности;
- хорошо ли читается текст;
- соответствует ли пост исходной истории.

Верни:

🔎 ПРОВЕРКА КАЧЕСТВА

📖 Смысл:
<сохранён / частично изменён / изменён>

➕ Новые факты:
<нет / обнаружены>

➖ Потерянные важные детали:
<нет / есть>

🎭 Драматизация:
<нет / умеренная / чрезмерная>

🔐 Анонимность:
<хорошая / требует проверки / плохая>

✍️ Качество текста:
<хорошее / требует редактирования / плохое>

📌 РЕКОМЕНДАЦИЯ:
<ГОТОВ / НУЖНО РЕДАКТИРОВАТЬ / НЕ ПУБЛИКОВАТЬ>

Комментарий:
<краткое объяснение>
"""

    user_prompt = f"""
ИСХОДНАЯ ИСТОРИЯ:

{story}


ГОТОВЫЙ ПОСТ:

{post_text if post_text else "Пост отсутствует."}
"""

    return await _ask_groq(
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.1,
        max_tokens=1500,
    )


# =========================================================
# STRUCTURED AI MODERATION
# =========================================================

async def moderate_story_json(
    story: str,
    post_text: str = "",
) -> dict[str, Any]:

    system_prompt = """
Ты выполняешь структурированную предварительную
модерацию пользовательской истории.

Верни ТОЛЬКО валидный JSON.

Структура:

{
  "risk": "low|medium|high|critical",
  "personal_data": "none|possible|found",
  "dangerous_content": false,
  "identification_risk": "low|medium|high",
  "post_quality": "good|review|bad",
  "issues": [],
  "recommendation": "publish|manual_review|reject",
  "reason": "..."
}

Не ставь диагнозы.

Не принимай окончательное решение вместо администратора.
"""

    user_prompt = f"""
История:

{story}

Пост:

{post_text if post_text else "Пост отсутствует."}
"""

    result = await _ask_groq(
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.0,
        max_tokens=1200,
    )

    # -----------------------------------------------------
    # Удаляем возможный markdown-блок JSON
    # -----------------------------------------------------

    cleaned = result.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace(
            "```json",
            "",
            1,
        )

        cleaned = cleaned.replace(
            "```",
            "",
        )

        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)

    except json.JSONDecodeError:
        # Если модель вернула неидеальный JSON,
        # сохраняем результат, не ломая бота.
        return {
            "risk": "medium",
            "personal_data": "possible",
            "dangerous_content": False,
            "identification_risk": "medium",
            "post_quality": "review",
            "issues": [
                "ИИ вернул ответ в неправильном формате."
            ],
            "recommendation": "manual_review",
            "reason": cleaned,
        }

    return data


# =========================================================
# SIMPLE TEST
# =========================================================

async def test_groq() -> bool:

    try:
        result = await _ask_groq(
            messages=[
                {
                    "role": "user",
                    "content": "Ответь одним словом: работает",
                }
            ],
            temperature=0.0,
            max_tokens=20,
        )

        print(
            f"✅ GROQ TEST OK: {result}"
        )

        return True

    except Exception as error:
        print(
            f"❌ GROQ TEST FAILED: {error}"
        )

        return False
