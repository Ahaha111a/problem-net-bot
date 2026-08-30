"""Standalone ProblemNet AI Worker."""
import asyncio
import logging
import os

# Worker receives jobs from Redis and is allowed to call AI providers directly.
os.environ["AI_WORKER_MODE"] = "1"
os.environ["AI_QUEUE_ENABLED"] = "0"

from ai import _ask_groq_direct
from ai_queue import worker_loop


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    print("🤖 ProblemNet AI Worker starting...")
    if not os.getenv("REDIS_URL", "").strip():
        raise RuntimeError("REDIS_URL не задан.")
    if not os.getenv("GROQ_API_KEY", "").strip():
        raise RuntimeError("GROQ_API_KEY не задан.")
    await worker_loop(_ask_groq_direct)


if __name__ == "__main__":
    asyncio.run(main())
