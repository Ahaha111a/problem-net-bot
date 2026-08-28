"""Redis-backed AI queue.

Основной и модераторский боты только ставят AI-задачу в очередь.
Отдельный ai_worker.py выполняет Groq-запросы.
"""
import asyncio
import json
import os
import uuid
from typing import Any

from redis.asyncio import Redis

QUEUE = os.getenv("AI_QUEUE_NAME", "problem-net:ai")
GROUP = os.getenv("AI_QUEUE_GROUP", "workers")
RESULT_TTL = int(os.getenv("AI_RESULT_TTL", "900"))


def _redis() -> Redis:
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise RuntimeError("REDIS_URL не задан. Подключите Redis в Railway.")
    return Redis.from_url(url, decode_responses=True)


async def _ensure_group(r: Redis):
    try:
        await r.xgroup_create(QUEUE, GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue_ai_job(messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
    job_id = uuid.uuid4().hex
    r = _redis()
    try:
        await _ensure_group(r)
        await r.xadd(QUEUE, {
            "job_id": job_id,
            "messages": json.dumps(messages, ensure_ascii=False),
            "temperature": str(temperature),
            "max_tokens": str(max_tokens),
        })
        return job_id
    finally:
        await r.aclose()


async def wait_ai_result(job_id: str, timeout: int = 300) -> str:
    r = _redis()
    key = f"{QUEUE}:result:{job_id}"
    try:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            value = await r.get(key)
            if value:
                data = json.loads(value)
                if data.get("ok"):
                    return data["result"]
                raise RuntimeError(data.get("error", "AI worker error"))
            await asyncio.sleep(0.5)
        raise TimeoutError("AI-задача не была выполнена за отведённое время")
    finally:
        await r.aclose()


async def worker_loop(handler):
    r = _redis()
    consumer = os.getenv("AI_WORKER_NAME", f"worker-{uuid.uuid4().hex[:8]}")
    await _ensure_group(r)
    try:
        while True:
            messages = await r.xreadgroup(GROUP, consumer, {QUEUE: ">"}, count=1, block=5000)
            if not messages:
                continue
            for _, entries in messages:
                for stream_id, fields in entries:
                    job_id = fields["job_id"]
                    key = f"{QUEUE}:result:{job_id}"
                    try:
                        result = await handler(
                            json.loads(fields["messages"]),
                            float(fields["temperature"]),
                            int(fields["max_tokens"]),
                        )
                        await r.set(key, json.dumps({"ok": True, "result": result}, ensure_ascii=False), ex=RESULT_TTL)
                    except Exception as exc:
                        await r.set(key, json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), ex=RESULT_TTL)
                    finally:
                        await r.xack(QUEUE, GROUP, stream_id)
    finally:
        await r.aclose()
