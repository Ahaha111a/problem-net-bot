#!/usr/bin/env python3
"""Fast CI smoke test: compile and import the production modules without secrets."""
import compileall
import importlib
import os
import sys

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("MODERATOR_BOT_TOKEN", "123456:TEST")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("CHANNEL_ID", "-1001234567890")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DATA_DIR", "/tmp/problemnet-data")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("AI_QUEUE_ENABLED", "0")

if not compileall.compile_dir("backend", quiet=1):
    raise SystemExit("Ошибка компиляции backend/")

sys.path.insert(0, "backend")
for name in [
    "config", "database", "ai", "ai_queue", "ai_worker",
    "post_generator", "ops", "staff_ops", "notifications",
    "handlers", "callbacks", "moderator_entry",
    "admin_api", "moderator_main", "user_main",
]:
    importlib.import_module(name)

print("PRE-DEPLOY CHECK: OK")
