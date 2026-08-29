"""Redis Streams queue for ProblemNet AI Worker."""
import asyncio
import json
import os
import uuid
from redis.asyncio import Redis

QUEUE = os.getenv("AI_QUEUE_NAME", "problem-net:ai")
GROUP = os.getenv("AI_QUEUE_GROUP", "workers")
RESULT_TTL = int(os.getenv("AI_RESULT_TTL", "900"))
CLAIM_IDLE_MS = int(os.getenv("AI_CLAIM_IDLE_MS", "120000"))
BLOCK_MS = int(os.getenv("AI_QUEUE_BLOCK_MS", "5000"))


def _redis() -> Redis:
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise RuntimeError("REDIS_URL не задан.")
    return Redis.from_url(url, decode_responses=True)


async def _ensure_group(r: Redis) -> None:
    try:
        await r.xgroup_create(QUEUE, GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue_ai_job(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    job_id = uuid.uuid4().hex
    r = _redis()
    try:
        await _ensure_group(r)
        await r.xadd(
            QUEUE,
            {
                "job_id": job_id,
                "messages": json.dumps(messages, ensure_ascii=False),
                "temperature": str(temperature),
                "max_tokens": str(max_tokens),
            },
        )
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
                    return str(data["result"])
                raise RuntimeError(data.get("error", "AI worker error"))
            await asyncio.sleep(0.5)
        raise TimeoutError("AI-задача не была выполнена за отведённое время")
    finally:
        await r.aclose()


async def _process_entry(r: Redis, stream_id: str, fields: dict, handler) -> None:
    job_id = fields.get("job_id", stream_id)
    key = f"{QUEUE}:result:{job_id}"
    try:
        result = await handler(
            json.loads(fields["messages"]),
            float(fields.get("temperature", "0.2")),
            int(fields.get("max_tokens", "1800")),
        )
        await r.set(
            key,
            json.dumps({"ok": True, "result": result}, ensure_ascii=False),
            ex=RESULT_TTL,
        )
    except Exception as exc:
        await r.set(
            key,
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
            ex=RESULT_TTL,
        )
    finally:
        await r.xack(QUEUE, GROUP, stream_id)


async def worker_loop(handler):
    r = _redis()
    consumer = os.getenv("AI_WORKER_NAME", f"worker-{uuid.uuid4().hex[:8]}")
    await _ensure_group(r)
    print(f"🤖 AI Worker Redis queue: {QUEUE}")
    print(f"👷 Consumer: {consumer}")

    try:
        while True:
            # First recover jobs left pending by a crashed worker.
            try:
                result = await r.xautoclaim(
                    QUEUE,
                    GROUP,
                    consumer,
                    min_idle_time=CLAIM_IDLE_MS,
                    start_id="0-0",
                    count=10,
                )
                next_id, entries = result[0], result[1]
                if entries:
                    for stream_id, fields in entries:
                        await _process_entry(r, stream_id, fields, handler)
                    continue
            except Exception as exc:
                print(f"⚠️ XAUTOCLAIM error: {exc}")

            messages = await r.xreadgroup(
                GROUP,
                consumer,
                {QUEUE: ">"},
                count=1,
                block=BLOCK_MS,
            )
            if not messages:
                continue

            for _, entries in messages:
                for stream_id, fields in entries:
                    await _process_entry(r, stream_id, fields, handler)
    finally:
        await r.aclose()
