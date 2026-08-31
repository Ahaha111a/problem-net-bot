import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import AsyncGroq



load_dotenv()


# =========================================================
# GROQ CONFIG
# =========================================================

# Database is optional inside the standalone AI Worker. The worker can
# run purely from environment variables; the user/moderator services use
# PostgreSQL-backed settings when available.
def _db_setting(key, default=None):
    if os.getenv("AI_WORKER_MODE", "0") == "1":
        env_map = {
            "ai_model": "GROQ_MODEL",
            "ai_fallback_model": "GROQ_FALLBACK_MODEL",
            "ai_temperature": "AI_TEMPERATURE",
            "ai_max_tokens": "AI_MAX_TOKENS",
        }
        return os.getenv(env_map.get(key, key.upper()), default)
    try:
        from database import get_setting
        return get_setting(key, default)
    except Exception:
        return os.getenv(key.upper(), default)


def _db_check_enabled(key):
    if os.getenv("AI_WORKER_MODE", "0") == "1":
        return os.getenv(f"AI_CHECK_{key.upper()}", "1").strip() == "1"
    try:
        from database import ai_check_enabled
        return ai_check_enabled(key)
    except Exception:
        return os.getenv(f"AI_CHECK_{key.upper()}", "1").strip() == "1"


def _log_error(service, message, details="", level="error"):
    try:
        from database import log_system_error
        log_system_error(service, message, details, level)
    except Exception:
        print(f"⚠️ {service}: {message} {details}")



GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b").strip()
GROQ_SAFETY_MODEL = os.getenv("GROQ_SAFETY_MODEL", "openai/gpt-oss-safeguard-20b").strip()
GROQ_MODELS = [
    x.strip()
    for x in os.getenv(
        "GROQ_MODELS",
        f"{GROQ_MODEL},{GROQ_FALLBACK_MODEL},qwen/qwen3.6-27b",
    ).split(",")
    if x.strip()
]


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
    model_override: str | None = None,
) -> str:
    """Непосредственный запрос к Groq. Вызывается только worker'ом или при аварийном режиме."""
    import asyncio
    import random

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY не задан в Railway Variables.")

    configured = []
    if not model_override:
        try:
            from database import get_ai_model_configs
            configured = [
                str(r["model"]).strip()
                for r in get_ai_model_configs()
                if bool(r["enabled"])
            ]
        except Exception:
            configured = []
    if not configured:
        configured = list(GROQ_MODELS)

    model = (model_override or _db_setting("ai_model", GROQ_MODEL) or GROQ_MODEL).strip()
    chain = []
    for candidate in [model, *configured, GROQ_FALLBACK_MODEL, "qwen/qwen3.6-27b"]:
        candidate = str(candidate or "").strip()
        if candidate and candidate not in chain:
            chain.append(candidate)
    try:
        temp = float(_db_setting("ai_temperature", str(temperature)))
    except Exception:
        temp = temperature
    try:
        tokens = int(_db_setting("ai_max_tokens", str(max_tokens)))
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

    last_error = None
    for candidate in chain:
        try:
            response = await call(candidate)
            if response.choices and response.choices[0].message.content:
                text = response.choices[0].message.content.strip()
                try:
                    from database import set_ai_model_health
                    set_ai_model_health(candidate, "ok", 0, 0, "Successful request")
                except Exception:
                    pass
                return text
            raise RuntimeError("Groq вернул пустой ответ.")
        except Exception as exc:
            last_error = exc
            status = getattr(exc, "status_code", None)
            _log_error("groq", str(exc), f"model={candidate}", "error")
            try:
                from database import set_ai_model_health
                set_ai_model_health(candidate, "error", 0, 1, str(exc))
            except Exception:
                pass
            if status in (401, 403):
                raise RuntimeError("Groq отклонил API-ключ. Проверьте GROQ_API_KEY в Railway Variables.") from exc

    raise RuntimeError(f"Все AI-модели недоступны: {last_error}") from last_error


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
        _log_error("ai-queue", str(queue_error), "Аварийный прямой режим", "warning")
        if os.getenv("AI_EMERGENCY_DIRECT", "1") == "1":
            return await _ask_groq_direct(messages, temperature, max_tokens)
        raise


# =========================================================
# STORY ANALYSIS
# =========================================================

async def analyze_story(story: str) -> str:
    if not _db_check_enabled("analysis"):
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
    if not _db_check_enabled("moderation"):
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
    if not _db_check_enabled("quality"):
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
    model_override: str | None = None,
) -> dict[str, Any]:
    if not _db_check_enabled("structured_moderation"):
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

    result = await (_ask_groq_direct if model_override else _ask_groq)(
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
        **({"model_override": model_override} if model_override else {}),
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
# AI SAFETY PIPELINE
# =========================================================

async def run_safety_pipeline(story: str, post_text: str = "", story_id: int | None = None) -> dict[str, Any]:
    """Layered safety pipeline. Any strong signal or model disagreement => human review."""
    import re
    from time import perf_counter

    # Deterministic gate: these signals never auto-publish.
    patterns = {
        "self_harm": r"(?:суицид|самоубий|покончить с собой|убить себя|порезать себя|самоповреж|не хочу жить|хочу умереть|хочу исчезнуть)",
        "violence": r"(?:убью|убить|застрел|зареж|напасть|избить|насил|угрожаю|угроза)",
        "dangerous_instructions": r"(?:как сделать бомбу|как изготовить взрыв|как отравить|как взломать|инструкция.*оруж)",
        "pii": r"(?:\b\+?\d[\d\s().-]{7,}\d\b|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    }
    deterministic = [name for name, pattern in patterns.items() if re.search(pattern, story, re.I)]

    generation_models = []
    try:
        from database import get_ai_model_configs
        generation_models = [
            str(r["model"]).strip() for r in get_ai_model_configs()
            if bool(r["enabled"]) and str(r["model"]).strip() != GROQ_SAFETY_MODEL
        ]
    except Exception:
        pass
    if not generation_models:
        generation_models = list(GROQ_MODELS)
    primary = generation_models[0] if generation_models else GROQ_MODEL
    secondary = generation_models[1] if len(generation_models) > 1 else GROQ_FALLBACK_MODEL

    started = perf_counter()
    primary_result = await moderate_story_json(story, post_text, model_override=primary)
    primary_latency = int((perf_counter() - started) * 1000)

    risk_map = {"low": 0.15, "medium": 0.45, "high": 0.75, "critical": 0.98}
    primary_risk = risk_map.get(str(primary_result.get("risk", "medium")).lower(), 0.5)
    primary_conf = float(primary_result.get("confidence", 0.8) or 0.8)

    second_result = None
    second_error = None
    if secondary and secondary != primary:
        try:
            second_result = await moderate_story_json(story, post_text, model_override=secondary)
        except Exception as exc:
            second_error = str(exc)

    # Dedicated safety model is independent from the content-generation models.
    safety_result = None
    safety_error = None
    if GROQ_SAFETY_MODEL and GROQ_SAFETY_MODEL not in {primary, secondary}:
        try:
            safety_result = await moderate_story_json(story, post_text, model_override=GROQ_SAFETY_MODEL)
        except Exception as exc:
            safety_error = str(exc)

    results = [x for x in (primary_result, second_result, safety_result) if x]
    risks = [risk_map.get(str(x.get("risk", "medium")).lower(), 0.5) for x in results]
    recommendations = [str(x.get("recommendation", "manual_review")).lower() for x in results]
    disagreement = len(set(recommendations)) > 1 or len(set(str(x.get("risk", "medium")).lower() for x in results)) > 1

    max_risk = max([primary_risk, *risks, 0.0])
    recommendation = "publish"
    if deterministic or max_risk >= 0.75 or disagreement or second_error or safety_error:
        recommendation = "manual_review"
    if any(str(x.get("personal_data", "none")).lower() == "found" for x in results) or any(str(x.get("identification_risk", "low")).lower() == "high" for x in results):
        recommendation = "manual_review"

    issues = []
    if deterministic:
        issues.extend([f"deterministic:{x}" for x in deterministic])
    for x in results:
        issues.extend([str(v) for v in (x.get("issues") or [])])
    issues = list(dict.fromkeys(issues))[:30]

    result = {
        "primary_model": primary,
        "secondary_model": secondary or None,
        "safety_model": GROQ_SAFETY_MODEL or None,
        "primary": primary_result,
        "secondary": second_result,
        "safety": safety_result,
        "disagreement": disagreement,
        "secondary_error": second_error,
        "safety_error": safety_error,
        "deterministic_flags": deterministic,
        "issues": issues,
        "risk_score": max_risk,
        "confidence": min([primary_conf, *[float(x.get("confidence", 0.6) or 0.6) for x in results]] or [0.55]),
        "recommendation": recommendation,
        "latency_ms": primary_latency,
        "required_human_review": recommendation == "manual_review",
    }

    if story_id is not None:
        try:
            from database import log_ai_safety_event, set_ai_model_health
            log_ai_safety_event(story_id, "deterministic_gate", "local-rules", recommendation == "publish", max_risk, result["confidence"], deterministic, json.dumps(result, ensure_ascii=False))
            for stage, model, item in (("primary", primary, primary_result), ("second_opinion", secondary, second_result), ("safety_model", GROQ_SAFETY_MODEL, safety_result)):
                if item and model:
                    log_ai_safety_event(story_id, stage, model, recommendation == "publish", risk_map.get(str(item.get("risk", "medium")).lower(), 0.5), float(item.get("confidence", 0.6) or 0.6), item.get("issues", []), json.dumps(item, ensure_ascii=False))
                    set_ai_model_health(model, "ok", primary_latency if model == primary else 0, 0, f"Safety stage: {stage}")
        except Exception as exc:
            _log_error("ai-safety", str(exc), f"story={story_id}", "warning")

    return result


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
