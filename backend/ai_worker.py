import asyncio
import os
import logging

# Worker bypasses queue and performs real Groq calls.
os.environ["AI_WORKER_MODE"] = "1"
os.environ.setdefault("AI_QUEUE_ENABLED", "0")

from ai import _ask_groq_direct
from ai_queue import worker_loop


async def main():
    logging.basicConfig(level=logging.INFO)
    print("🤖 AI worker запущен")
    await worker_loop(_ask_groq_direct)


if __name__ == "__main__":
    asyncio.run(main())
