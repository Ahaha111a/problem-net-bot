# «Проблем нет» — production-архитектура

## Сервисы Railway

1. **User Bot** — `python backend/user_main.py`
2. **Moderator Bot + Mini App** — `python backend/moderator_main.py`
3. **AI Worker** — `python backend/ai_worker.py`
4. **PostgreSQL** — Railway Database
5. **Redis** — Railway Database

User Bot и Moderator Bot больше не должны хранить рабочую БД в локальном `bot.db`.
Для production оба сервиса используют одну `DATABASE_URL` PostgreSQL. Это устраняет сброс статистики между деплоями и проблему общего SQLite-файла.

## Railway Variables

На User Bot, Moderator Bot и AI Worker:

```text
BOT_TOKEN=...
ADMIN_IDS=123456789
CHANNEL_ID=-100...
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
TIMEZONE=Europe/Moscow
AI_QUEUE_ENABLED=1
AI_EMERGENCY_DIRECT=1
AI_JOB_TIMEOUT=300
```

Только Moderator Bot:

```text
MODERATOR_BOT_TOKEN=...
ADMIN_MINIAPP_URL=https://ВАШ-MODERATOR-DOMAIN/admin
```

AI Worker:

```text
AI_WORKER_NAME=ai-worker-1
```

## PostgreSQL: миграция существующего bot.db

Сначала сделайте копию старого `bot.db`.

Затем один раз запустите:

```bash
SQLITE_DB_PATH=/app/data/bot.db DATABASE_URL="$DATABASE_URL" python scripts/migrate_sqlite_to_postgres.py
```

После проверки данных User Bot и Moderator Bot должны использовать `DATABASE_URL`.
`DB_PATH` оставьте только как аварийный SQLite-режим.

## Volume

Если PostgreSQL и Redis используются как Railway Database services, Volume для **User Bot** и **Moderator Bot** не нужен для самой БД.

Volume нужен только для локальных файлов, которые должны переживать redeploy. Например, если вы хотите хранить локальные резервные копии JSON.gz, можно подключить Volume к Moderator Bot в `/app/data`.

Railway отдельно хранит данные PostgreSQL/Redis как database services. Railway рекомендует persistent storage для stateful services; обычная файловая система приложения без Volume является ephemeral. citeturn0search1turn0search8

## Healthcheck

Railway проверяет `/health`. Он должен отвечать HTTP 200.

Не ставьте healthcheck на API, который требует Telegram авторизацию или PostgreSQL.

Railway использует healthcheck именно во время deployment, поэтому `/health` должен быть простым liveness endpoint. citeturn0search7

## Redis

Redis используется для AI-очереди и rate limiting.
Railway автоматически предоставляет `REDIS_URL`. citeturn0search9

## AI Worker

Основные боты не выполняют тяжёлые AI-запросы напрямую, если `AI_QUEUE_ENABLED=1`.
Они ставят задачу в Redis Stream.
AI Worker получает задачу, вызывает Groq и возвращает результат.

Если Redis/worker временно недоступны, включается аварийный прямой режим (`AI_EMERGENCY_DIRECT=1`).

Groq рекомендует client-side throttling и exponential backoff для 429/5xx. В коде это уже предусмотрено. citeturn0search15turn0search14

## Резервные копии PostgreSQL

Автоматическая копия создаётся мониторингом Moderator Bot.
Также вручную:

```bash
DATABASE_URL="$DATABASE_URL" python scripts/backup_postgres.py
```

Восстановление:

```bash
DATABASE_URL="$DATABASE_URL" python scripts/restore_postgres.py /path/to/problem_net_YYYYMMDD_HHMMSS.json.gz
```

Для production также рекомендуется включить Railway backups/PITR и периодически проводить restore drill. citeturn0search12

## Pre-deploy

Перед deploy:

```bash
python scripts/test_before_deploy.py
```

В GitHub Actions можно запускать этот тест на каждый push.

## Staging → Production

Рекомендуемый процесс:

```text
GitHub PR
  ↓
Staging Railway environment
  ↓
python scripts/test_before_deploy.py
  ↓
проверка Mini App / AI / БД
  ↓
Production
```

## Папки GitHub

```text
problem-net/
├── backend/
│   ├── user_main.py
│   ├── moderator_main.py
│   ├── ai_worker.py
│   ├── ai_queue.py
│   ├── admin_api.py
│   ├── database.py
│   ├── ai.py
│   ├── post_generator.py
│   ├── rate_limit.py
│   └── ...
├── scripts/
│   ├── migrate_sqlite_to_postgres.py
│   ├── backup_postgres.py
│   ├── restore_postgres.py
│   └── test_before_deploy.py
├── requirements.txt
├── railway.json
└── .env.example
```

Папку `scripts` теперь удалять не нужно: она содержит production-инструменты миграции, backup/restore и pre-deploy проверки.
