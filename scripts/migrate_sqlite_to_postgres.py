#!/usr/bin/env python3
"""Однократная безопасная миграция существующего bot.db в PostgreSQL.

Запуск:
  DATABASE_URL='postgresql://...' python scripts/migrate_sqlite_to_postgres.py

Скрипт не удаляет SQLite-файл. Сначала создаёт схему PostgreSQL через текущую
init_db(), затем переносит данные таблица-за-таблицей с ON CONFLICT DO NOTHING.
"""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

sqlite_path = Path(os.getenv("SQLITE_DB_PATH", "/app/data/bot.db"))
database_url = os.getenv("DATABASE_URL", "").strip()
if not database_url:
    raise SystemExit("DATABASE_URL не задан")
if not sqlite_path.exists():
    raise SystemExit(f"SQLite база не найдена: {sqlite_path}")

# Сначала создаём PostgreSQL-схему.
os.environ["DATABASE_URL"] = database_url
sys.path.insert(0, str(ROOT / "backend"))
import database as db

db.init_db()
db.ensure_platform_defaults()

import psycopg

src = sqlite3.connect(sqlite_path)
src.row_factory = sqlite3.Row

def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'

with psycopg.connect(database_url) as dst:
    with dst.cursor() as cur:
        tables = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for table in tables:
            rows = src.execute(f"SELECT * FROM {qident(table)}").fetchall()
            if not rows:
                continue
            columns = [d[0] for d in src.execute(f"SELECT * FROM {qident(table)} LIMIT 0").description]
            cols = ', '.join(qident(c) for c in columns)
            placeholders = ', '.join(['%s'] * len(columns))
            sql = f"INSERT INTO {qident(table)} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            for row in rows:
                cur.execute(sql, tuple(row[c] for c in columns))
            if 'id' in columns:
                try:
                    cur.execute(f"SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), true) FROM {qident(table)}", (table,))
                except Exception:
                    pass
            print(f"✓ {table}: {len(rows)} строк")
    dst.commit()

src.close()
print("\nМиграция завершена. SQLite-файл сохранён без изменений.")
