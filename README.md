# «Проблем нет» — новая production-структура

## Архитектура

Проект разделён на два Telegram-бота:

- `user_main.py` — только пользовательский бот.
- `moderator_main.py` — бот сотрудников + Mini App + планировщик + мониторинг + отчёты.

Оба сервиса используют одну и ту же базу данных.

## GitHub

Рекомендуемая структура:

```text
problem-net/
├── backend/
│   ├── __init__.py
│   ├── user_main.py
│   ├── moderator_main.py
│   ├── moderator_entry.py
│   ├── user_handlers.py
│   ├── handlers.py
│   ├── callbacks.py
│   ├── keyboards.py
│   ├── states.py
│   ├── config.py
│   ├── database.py
│   ├── ai.py
│   ├── post_generator.py
│   ├── admin_api.py
│   └── miniapp/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── scripts/
├── requirements.txt
├── railway.json
└── .env.example
```

## Railway — два сервиса из одного GitHub-репозитория

### Сервис 1 — User Bot

Start Command:

```bash
python backend/user_main.py
```

### Сервис 2 — Moderator Bot + Mini App

Start Command:

```bash
python backend/moderator_main.py
```

Оба сервиса должны использовать один GitHub repository и одну ветку.

## Variables

На обоих сервисах:

```text
BOT_TOKEN=токен пользовательского бота
ADMIN_IDS=123456789
CHANNEL_ID=-100...
GROQ_API_KEY=gsk_...
TIMEZONE=Europe/Moscow
DB_PATH=bot.db
DATA_DIR=/app/data
```

Только на Moderator Bot:

```text
MODERATOR_BOT_TOKEN=токен второго бота
ADMIN_MINIAPP_URL=https://YOUR-DOMAIN/admin
```

## Persistent Volume

На сервисе Moderator Bot подключить Railway Volume с mount path:

```text
/app/data
```

База будет:

```text
/app/data/bot.db
```

Резервные копии:

```text
/app/data/backups/
```

## Важное

Не удаляйте старый `bot.db`, пока не проверена новая база и Volume.

После подключения Volume выполните redeploy.
