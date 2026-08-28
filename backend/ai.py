import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import AsyncGroq

from database import get_setting, ai_check_enabled, log_system_error


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

async def _ask_groq_direct(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """Непосредственный запрос к Groq. Вызывается только worker'ом или при аварийном режиме."""
    import asyncio
    import random

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY не задан в Railway Variables.")

    model = get_setting("ai_model", GROQ_MODEL) or GROQ_MODEL
    fallback = get_setting("ai_fallback_model", os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant"))
    try:
        temp = float(get_setting("ai_temperature", str(temperature)))
    except Exception:
        temp = temperature
    try:
        tokens = int(get_setting("ai_max_tokens", str(max_tokens)))
    except Exception:
        tokens = max_tokens

    async def call(model_name):
        groq = AsyncGroq(api_key=api_key)
        attempts = 4
        for attempt in range(attempts):
            try:
                return await groq.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                )
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                retryable = status == 429 or (isinstance(status, int) and status >= 500)
                if not retryable or attempt == attempts - 1:
                    raise
                retry_after = getattr(exc, "response", None)
                delay = min(20, 2 ** attempt + random.random())
                if retry_after is not None:
                    try:
                        header = retry_after.headers.get("retry-after")
                        if header:
                            delay = min(30, float(header))
                    except Exception:
                        pass
                await asyncio.sleep(delay)

    try:
        response = await call(model)
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        raise RuntimeError("Groq вернул пустой ответ.")
    except Exception as first_error:
        log_system_error("groq", str(first_error), f"model={model}", "error")
        status = getattr(first_error, "status_code", None)
        # 401/403 are configuration errors: switching models cannot fix the key.
        if status in (401, 403):
            raise RuntimeError("Groq отклонил API-ключ. Проверьте GROQ_API_KEY в Railway Variables.") from first_error
        if fallback and fallback != model:
            try:
                response = await call(fallback)
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
            except Exception as second_error:
                log_system_error("groq", str(second_error), f"fallback={fallback}", "error")
        raise first_error


async def _ask_groq(
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """Очередь AI. При падении Redis включается аварийный прямой режим."""
    if os.getenv("AI_WORKER_MODE", "0") == "1" or os.getenv("AI_QUEUE_ENABLED", "0") != "1":
        return await _ask_groq_direct(messages, temperature, max_tokens)

    try:
        from ai_queue import enqueue_ai_job, wait_ai_result
        job_id = await enqueue_ai_job(messages, temperature, max_tokens)
        return await wait_ai_result(job_id, int(os.getenv("AI_JOB_TIMEOUT", "300")))
    except Exception as queue_error:
        log_system_error("ai-queue", str(queue_error), "Аварийный прямой режим", "warning")
        if os.getenv("AI_EMERGENCY_DIRECT", "1") == "1":
            return await _ask_groq_direct(messages, temperature, max_tokens)
        raise


# =========================================================
# STORY ANALYSIS
# =========================================================

async def analyze_story(story: str) -> str:
    if not ai_check_enabled("analysis"):
        return "ℹ️ Проверка анализа ИИ отключена в настройках."

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
    if not ai_check_enabled("moderation"):
        return "ℹ️ ИИ-модерация отключена в настройках."

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
    if not ai_check_enabled("quality"):
        return "ℹ️ Проверка качества ИИ отключена в настройках."

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
    if not ai_check_enabled("structured_moderation"):
        return {"risk":"medium","personal_data":"possible","dangerous_content":False,"identification_risk":"medium","post_quality":"review","issues":["Проверка отключена"],"recommendation":"manual_review","reason":"Проверка отключена в настройках проекта."}

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
