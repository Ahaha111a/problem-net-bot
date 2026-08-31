"""Standalone ProblemNet AI Worker."""
import asyncio
import logging
import os
from aiohttp import web

# Worker receives jobs from Redis and calls AI providers directly.
os.environ["AI_QUEUE_ENABLED"] = "0"
os.environ["AI_WORKER_MODE"] = "1"

from ai import _ask_groq_direct
from ai_queue import worker_loop


async def _health_server():
    app = web.Application()

    async def health(request):
        return web.json_response({
            "ok": True,
            "service": "problemnet-ai-worker",
            "redis": bool(os.getenv("REDIS_URL", "").strip()),
            "groq": bool(os.getenv("GROQ_API_KEY", "").strip()),
        })

    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", os.getenv("AI_WORKER_PORT", "8080")))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    return runner


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

    health_runner = await _health_server()
    try:
        while True:
            try:
                await worker_loop(_ask_groq_direct)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logging.exception("AI Worker loop crashed: %s", exc)
                await asyncio.sleep(5)
    finally:
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
