import os
import re
import json
from pathlib import Path


# =========================================================
# DATABASE BACKEND
# =========================================================
# PostgreSQL is the shared production database for both bots.
# SQLite remains supported for local development / emergency mode.

_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
DATA_DIR = (_volume or os.getenv("DATA_DIR", "/app/data").strip() or "/app/data")
_raw_db = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"
DB_PATH = Path(_raw_db if os.path.isabs(_raw_db) else str(Path(DATA_DIR) / _raw_db))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = True

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан. После перехода на PostgreSQL SQLite больше не используется.")

# DB_PATH is retained only for backwards-compatible backup configuration.
# Production uses PostgreSQL, so do not create a local /app/data directory on
# import (Railway containers may not have a writable path there).
if not DATABASE_URL and DB_PATH.parent and str(DB_PATH.parent) != ".":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class _HybridRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def _pg_row(cursor):
    cols = [d.name for d in cursor.description]
    values = cursor.fetchone()
    if values is None:
        return None
    return _HybridRow(zip(cols, values))


def _translate_sql(sql: str) -> str:
    """Translate the small SQLite syntax subset still present in legacy queries.

    The application now talks only to PostgreSQL; this adapter exists solely so
    existing handlers/database calls can be migrated without rewriting 2000+
    lines at once. New code should use PostgreSQL syntax directly.
    """
    sql = sql.replace("?", "%s")

    # INSERT OR IGNORE -> PostgreSQL ON CONFLICT.
    sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, flags=re.I)
    # Do not add a second ON CONFLICT clause to statements that already
    # contain one.  The previous implementation only looked for the exact
    # substring " ON CONFLICT " and therefore missed forms such as
    # "ON CONFLICT(key)", producing invalid PostgreSQL.
    if (
        re.search(r"\bINSERT\s+INTO\b", sql, flags=re.I)
        and not re.search(r"\bON\s+CONFLICT(?:\s*\(|\s+DO\b)", sql, flags=re.I)
    ):
        # Only append for INSERT statements. For INSERT ... SELECT this is also
        # valid PostgreSQL syntax.
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    # SQLite AUTOINCREMENT -> PostgreSQL sequence-backed bigint.
    sql = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "BIGSERIAL PRIMARY KEY", sql, flags=re.I)

    # Date/time compatibility. All application times are interpreted in Moscow
    # time for business logic; timestamps remain PostgreSQL timestamps.
    sql = re.sub(
        r"date\('now',\s*'([+-]\d+)\s+days?'\)",
        r"((CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date + INTERVAL '\1 days')::date",
        sql, flags=re.I,
    )
    sql = re.sub(
        r"date\('now'\)",
        "(CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date",
        sql, flags=re.I,
    )
    sql = re.sub(
        r"datetime\('now',\s*'([^']+)'\)",
        r"(CURRENT_TIMESTAMP + INTERVAL '\1')",
        sql, flags=re.I,
    )
    sql = re.sub(
        r"datetime\('now',\s*%s\)",
        "(CURRENT_TIMESTAMP + (%s)::interval)",
        sql, flags=re.I,
    )
    sql = re.sub(r"datetime\('now'\)", "CURRENT_TIMESTAMP", sql, flags=re.I)
    sql = re.sub(r"datetime\(([^(),]+)\)", r"\1::timestamp", sql, flags=re.I)
    sql = re.sub(r"date\(([^(),]+)\)", r"\1::date", sql, flags=re.I)

    # SQLite julianday(a)-julianday(b) -> PostgreSQL epoch difference in days.
    sql = re.sub(
        r"julianday\(([^()]+)\)\s*-\s*julianday\(([^()]+)\)",
        r"EXTRACT(EPOCH FROM (\1::timestamp - \2::timestamp)) / 86400.0",
        sql, flags=re.I,
    )
    sql = re.sub(
        r"strftime\('%H',\s*([^()]+)\)",
        r"EXTRACT(HOUR FROM \1::timestamp)",
        sql, flags=re.I,
    )
    return sql


class _PGCursor:
    def __init__(self, raw):
        self.raw = raw
        self.lastrowid = None

    def execute(self, sql, params=None):
        sql = _translate_sql(sql)
        # The application relies on lastrowid in exactly three places.
        low = sql.lstrip().lower()
        needs_id = low.startswith("insert into stories") or low.startswith("insert into support_dialogs") or low.startswith("insert into repost_jobs")
        if needs_id and " returning " not in low:
            sql += " RETURNING id"
        self.raw.execute(sql, params or ())
        if needs_id:
            row = self.raw.fetchone()
            self.lastrowid = row[0] if row else None
        return self

    def executemany(self, sql, seq):
        self.raw.executemany(_translate_sql(sql), seq)
        return self

    def fetchone(self):
        row = self.raw.fetchone()
        if row is None:
            return None
        return _HybridRow(zip([d.name for d in self.raw.description], row))

    def fetchall(self):
        rows = self.raw.fetchall()
        cols = [d.name for d in self.raw.description] if self.raw.description else []
        return [_HybridRow(zip(cols, row)) for row in rows]

    def __getattr__(self, name):
        return getattr(self.raw, name)


class _PGConnection:
    def __init__(self):
        import psycopg
        self.raw = psycopg.connect(DATABASE_URL)

    def cursor(self):
        return _PGCursor(self.raw.cursor())

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def executescript(self, script):
        for statement in script.split(';'):
            statement = statement.strip()
            if statement:
                self.execute(statement)
        return self

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def get_connection():
    """Open a short-lived PostgreSQL connection with startup/network retries.

    The project intentionally keeps the existing synchronous DB API for now,
    but transient Supabase/Railway network hiccups should not immediately crash
    a Telegram worker.
    """
    import time

    last_error = None
    for attempt in range(1, 4):
        try:
            return _PGConnection()
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.75 * attempt)
    raise RuntimeError(f"PostgreSQL connection failed after 3 attempts: {last_error}") from last_error


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():
    """Apply PostgreSQL Alembic migrations safely in production.

    Both Telegram services can start at the same time, so migration work is
    serialized with a PostgreSQL advisory lock. The Alembic version column is
    widened before Alembic writes any revision, including on a brand-new DB.
    This removes the old VARCHAR(32) trap permanently.
    """
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    import psycopg

    root = Path(__file__).resolve().parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    versions_dir = root / "alembic" / "versions"
    if not versions_dir.is_dir():
        raise RuntimeError(f"Alembic migrations not found: {versions_dir}")
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

    lock_key = 726391
    with psycopg.connect(DATABASE_URL) as lock_con:
        lock_con.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
        try:
            # Alembic's default version_num is VARCHAR(32). The project uses
            # descriptive revision names, some longer than 32 characters.
            # Create the table ourselves on a fresh database, or widen it on
            # an existing database, before Alembic performs any upgrade.
            exists = lock_con.execute(
                "SELECT to_regclass('public.alembic_version')"
            ).fetchone()[0]
            if exists is None:
                lock_con.execute(
                    "CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL PRIMARY KEY)"
                )
            else:
                lock_con.execute(
                    "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
                )
            lock_con.commit()

            command.upgrade(cfg, "head")
        finally:
            lock_con.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))

    ensure_platform_defaults()
    try:
        from ops import ensure_ops_defaults
        ensure_ops_defaults()
    except Exception as exc:
        print(f"⚠️ Ops defaults skipped: {exc}")

# =========================================================
# USERS
# =========================================================

def _random_next_notification_iso():
    import random
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    # Следующее уведомление ровно через 24 часа.
    # Время первого уведомления случайное, затем интервал сохраняется ровно 24 часа.
    next_day = now + timedelta(days=1)
    random_hour = random.randint(9, 22)
    random_minute = random.randint(0, 59)
    scheduled = next_day.replace(hour=random_hour, minute=random_minute, second=0, microsecond=0)
    return scheduled.isoformat()


def register_user(user_id: int):
    connection = get_connection()
    row = connection.execute(
        "SELECT user_id, notification_at FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO users (user_id, notification_at) VALUES (?, ?)",
            (user_id, _random_next_notification_iso()),
        )
    elif not row["notification_at"]:
        connection.execute(
            "UPDATE users SET notification_at = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (_random_next_notification_iso(), user_id),
        )
    connection.commit()
    connection.close()


def get_due_notification_users(now_iso: str):
    connection = get_connection()
    rows = connection.execute(
        "SELECT user_id FROM users WHERE notification_at IS NOT NULL AND datetime(notification_at) <= datetime(?) ORDER BY user_id",
        (now_iso,),
    ).fetchall()
    connection.close()
    return [row["user_id"] for row in rows]


def mark_notification_sent(user_id: int):
    connection = get_connection()
    connection.execute(
        "UPDATE users SET notification_at = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (_random_next_notification_iso(), user_id),
    )
    connection.commit()
    connection.close()



def get_user_count():
    connection = get_connection()
    row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    connection.close()
    return row["count"] if row else 0


def get_support_stats():
    connection = get_connection()
    open_count = connection.execute(
        "SELECT COUNT(*) AS count FROM support_dialogs WHERE status = 'open'"
    ).fetchone()["count"]
    new_count = connection.execute(
        "SELECT COUNT(*) AS count FROM support_dialogs WHERE status = 'open' AND support_status = 'new'"
    ).fetchone()["count"]
    in_progress = connection.execute(
        "SELECT COUNT(*) AS count FROM support_dialogs WHERE status = 'open' AND support_status = 'in_progress'"
    ).fetchone()["count"]
    connection.close()
    return {"open": open_count, "new": new_count, "in_progress": in_progress}


def get_extended_stats():
    connection = get_connection()
    published_today = connection.execute(
        """SELECT COUNT(*) AS count FROM stories
           WHERE status = 'published'
             AND date(created_at) = date('now')"""
    ).fetchone()["count"]
    rejected_today = connection.execute(
        """SELECT COUNT(*) AS count FROM stories
           WHERE status = 'rejected'
             AND date(created_at) = date('now')"""
    ).fetchone()["count"]
    avg_dialog_messages = connection.execute(
        """SELECT COALESCE(AVG(cnt), 0) AS value FROM (
               SELECT COUNT(*) AS cnt FROM support_messages GROUP BY dialog_id
           )"""
    ).fetchone()["value"]
    connection.close()
    stats = get_stats()
    stats["users"] = get_user_count()
    stats["support"] = get_support_stats()
    stats["published_today"] = published_today
    stats["rejected_today"] = rejected_today
    stats["avg_dialog_messages"] = round(float(avg_dialog_messages or 0), 1)
    return stats

# =========================================================
# STORIES
# =========================================================

def create_story(
    user_id: int,
    text: str,
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO stories (
            user_id,
            text,
            status
        )
        VALUES (?, ?, 'waiting')
        """,
        (
            user_id,
            text,
        ),
    )

    story_id = cursor.lastrowid

    connection.commit()

    connection.close()

    return story_id


def update_ai_result(
    story_id: int,
    ai_result: str,
):
    import re

    category = None
    match = re.search(r"🏷\s*Тема:\s*([^\n]+)", ai_result or "")
    if match:
        category = match.group(1).strip()

    connection = get_connection()
    connection.execute(
        """
        UPDATE stories
        SET ai_result = ?, category = ?
        WHERE id = ?
        """,
        (ai_result, category, story_id),
    )
    connection.commit()
    connection.close()


def update_post(
    story_id: int,
    post_text: str,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET post_text = ?
        WHERE id = ?
        """,
        (
            post_text,
            story_id,
        ),
    )

    connection.commit()

    connection.close()


def get_story(
    story_id: int,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM stories
        WHERE id = ?
        """,
        (
            story_id,
        ),
    ).fetchone()

    connection.close()

    return row


def publish_story(story_id: int, channel_message_id: int | None = None):
    connection = get_connection()
    if channel_message_id is None:
        connection.execute(
            "UPDATE stories SET status = 'published' WHERE id = ?",
            (story_id,),
        )
    else:
        connection.execute(
            """UPDATE stories
               SET status = 'published', channel_message_id = ?
               WHERE id = ?""",
            (channel_message_id, story_id),
        )
    connection.commit()
    connection.close()


def reject_story(story_id: int, reason: str | None = None):
    connection = get_connection()
    connection.execute(
        """UPDATE stories
           SET status = 'rejected', rejection_reason = ?
           WHERE id = ?""",
        (reason, story_id),
    )
    connection.commit()
    connection.close()


def get_waiting_stories():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM stories
        WHERE status = 'waiting'
          AND scheduled_at IS NULL
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return rows


def get_all_stories():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM stories
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return rows


def get_stats():

    connection = get_connection()

    total = connection.execute(
        """
        SELECT COUNT(*)
        FROM stories
        """
    ).fetchone()[0]

    waiting = connection.execute(
        """
        SELECT COUNT(*)
        FROM stories
        WHERE status = 'waiting'
        """
    ).fetchone()[0]

    published = connection.execute(
        """
        SELECT COUNT(*)
        FROM stories
        WHERE status = 'published'
        """
    ).fetchone()[0]

    rejected = connection.execute(
        """
        SELECT COUNT(*)
        FROM stories
        WHERE status = 'rejected'
        """
    ).fetchone()[0]

    connection.close()

    return {
        "total": total,
        "waiting": waiting,
        "published": published,
        "rejected": rejected,
    }


# =========================================================
# REACTIONS
# =========================================================

def set_story_reaction(story_id: int, user_id: int, reaction: str | None):
    connection = get_connection()
    if reaction is None:
        connection.execute(
            "DELETE FROM story_reactions WHERE story_id = ? AND user_id = ?",
            (story_id, user_id),
        )
    else:
        connection.execute(
            """
            INSERT INTO story_reactions (story_id, user_id, reaction)
            VALUES (?, ?, ?)
            ON CONFLICT(story_id, user_id)
            DO UPDATE SET reaction = excluded.reaction
            """,
            (story_id, user_id, reaction),
        )
    connection.commit()
    connection.close()


def get_story_reaction_counts(story_id: int):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT reaction, COUNT(*) AS count
        FROM story_reactions
        WHERE story_id = ?
        GROUP BY reaction
        """,
        (story_id,),
    ).fetchall()
    connection.close()
    result = {"heart": 0, "understand": 0, "support": 0}
    for row in rows:
        result[row["reaction"]] = row["count"]
    return result


def get_user_story_reaction(story_id: int, user_id: int):
    connection = get_connection()
    row = connection.execute(
        "SELECT reaction FROM story_reactions WHERE story_id = ? AND user_id = ?",
        (story_id, user_id),
    ).fetchone()
    connection.close()
    return row["reaction"] if row else None


def get_total_reactions():
    connection = get_connection()
    row = connection.execute("SELECT COUNT(*) AS count FROM story_reactions").fetchone()
    connection.close()
    return row["count"] if row else 0


# =========================================================
# AI MODERATION RESULT
# =========================================================

def update_ai_moderation_result(story_id: int, result: str):
    connection = get_connection()
    connection.execute(
        "UPDATE stories SET ai_moderation_result = ? WHERE id = ?",
        (result, story_id),
    )
    connection.commit()
    connection.close()


def get_ai_moderation_result(story_id: int):
    connection = get_connection()
    row = connection.execute(
        "SELECT ai_moderation_result FROM stories WHERE id = ?",
        (story_id,),
    ).fetchone()
    connection.close()
    return row["ai_moderation_result"] if row else None


# =========================================================
# ADMIN AUDIT LOG
# =========================================================

def log_admin_action(
    admin_id: int,
    action: str,
    story_id: int | None = None,
    dialog_id: int | None = None,
    user_id: int | None = None,
    details: str | None = None,
):
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO admin_audit_log
            (admin_id, action, story_id, dialog_id, user_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (admin_id, action, story_id, dialog_id, user_id, details),
    )
    connection.commit()
    connection.close()


def get_admin_audit(limit: int = 50):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT *
        FROM admin_audit_log
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    connection.close()
    return rows


def get_reaction_stats():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT reaction, COUNT(*) AS count
        FROM story_reactions
        GROUP BY reaction
        """
    ).fetchall()
    connection.close()
    result = {"heart": 0, "understand": 0, "support": 0}
    for row in rows:
        result[row["reaction"]] = row["count"]
    return result


# =========================================================
# SCHEDULED PUBLICATIONS (W)
# =========================================================

def schedule_story(story_id: int, scheduled_at: str, admin_id: int):
    connection = get_connection()
    cursor = connection.execute(
        """
        UPDATE stories
        SET scheduled_at = ?, scheduled_by = ?
        WHERE id = ? AND status = 'waiting'
        """,
        (scheduled_at, admin_id, story_id),
    )
    connection.commit()
    changed = cursor.rowcount > 0
    connection.close()
    return changed


def cancel_scheduled_story(story_id: int):
    connection = get_connection()
    cursor = connection.execute(
        """
        UPDATE stories
        SET scheduled_at = NULL, scheduled_by = NULL
        WHERE id = ? AND status = 'waiting'
        """,
        (story_id,),
    )
    connection.commit()
    changed = cursor.rowcount > 0
    connection.close()
    return changed


def get_scheduled_stories(limit: int = 100):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT * FROM stories
        WHERE status = 'waiting' AND scheduled_at IS NOT NULL
        ORDER BY datetime(scheduled_at) ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    connection.close()
    return rows


def get_due_scheduled_stories(now_iso: str, limit: int = 20):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT * FROM stories
        WHERE status = 'waiting'
          AND scheduled_at IS NOT NULL
          AND datetime(scheduled_at) <= datetime(?)
        ORDER BY datetime(scheduled_at) ASC
        LIMIT ?
        """,
        (now_iso, limit),
    ).fetchall()
    connection.close()
    return rows


def claim_scheduled_story(story_id: int):
    connection = get_connection()
    cursor = connection.execute(
        """
        UPDATE stories
        SET status = 'publishing'
        WHERE id = ? AND status = 'waiting' AND scheduled_at IS NOT NULL
        """,
        (story_id,),
    )
    connection.commit()
    changed = cursor.rowcount > 0
    connection.close()
    return changed


def release_scheduled_story(story_id: int, retry_at: str):
    connection = get_connection()
    connection.execute(
        """
        UPDATE stories
        SET status = 'waiting', scheduled_at = ?
        WHERE id = ? AND status = 'publishing'
        """,
        (retry_at, story_id),
    )
    connection.commit()
    connection.close()


def get_analytics():
    connection = get_connection()
    total_users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_stories = connection.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
    published = connection.execute("SELECT COUNT(*) FROM stories WHERE status = 'published'").fetchone()[0]
    rejected = connection.execute("SELECT COUNT(*) FROM stories WHERE status = 'rejected'").fetchone()[0]
    waiting = connection.execute("SELECT COUNT(*) FROM stories WHERE status = 'waiting' AND scheduled_at IS NULL").fetchone()[0]
    scheduled = connection.execute("SELECT COUNT(*) FROM stories WHERE status = 'waiting' AND scheduled_at IS NOT NULL").fetchone()[0]
    publishing = connection.execute("SELECT COUNT(*) FROM stories WHERE status = 'publishing'").fetchone()[0]
    reactions = connection.execute("SELECT COUNT(*) FROM story_reactions").fetchone()[0]
    dialogs = connection.execute("SELECT COUNT(*) FROM support_dialogs").fetchone()[0]
    open_dialogs = connection.execute("SELECT COUNT(*) FROM support_dialogs WHERE status = 'open'").fetchone()[0]
    messages = connection.execute("SELECT COUNT(*) FROM support_messages").fetchone()[0]
    categories = connection.execute(
        """SELECT COALESCE(category, 'Не определена') AS category, COUNT(*) AS count
           FROM stories GROUP BY category ORDER BY count DESC LIMIT 10"""
    ).fetchall()
    daily = connection.execute(
        """SELECT date(created_at) AS day, COUNT(*) AS count
           FROM stories WHERE created_at >= date('now', '-6 days')
           GROUP BY date(created_at) ORDER BY day ASC"""
    ).fetchall()
    connection.close()
    return {
        'users': total_users,
        'stories': total_stories,
        'published': published,
        'rejected': rejected,
        'waiting': waiting,
        'scheduled': scheduled,
        'publishing': publishing,
        'reactions': reactions,
        'dialogs': dialogs,
        'open_dialogs': open_dialogs,
        'messages': messages,
        'categories': categories,
        'daily': daily,
    }


# =========================================================
# BACKUPS (X)
# =========================================================

def backup_database(backup_dir: str | None = None):
    """Автоматическая резервная копия PostgreSQL или SQLite."""
    from datetime import datetime
    import subprocess

    target_dir = Path(backup_dir or os.getenv('BACKUP_DIR', '') or str(DB_PATH.parent / 'backups'))
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    import gzip, json
    target = target_dir / f'problem_net_{stamp}.json.gz'
    con = get_connection()
    tables = [r['tablename'] for r in con.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()]
    payload = {'created_at': datetime.utcnow().isoformat(), 'tables': {}}
    for table in tables:
        safe_table = table.replace('"', '""')
        rows = con.execute(f'SELECT * FROM "{safe_table}"').fetchall()
        payload['tables'][table] = [dict(r) for r in rows]
    con.close()
    with gzip.open(target, 'wt', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, default=str)
    backups = sorted(target_dir.glob('problem_net_*.json.gz'), key=lambda x: x.stat().st_mtime, reverse=True)

    for old in backups[14:]:
        try: old.unlink()
        except OSError: pass
    return str(target)

# =========================================================
# ADMIN ROLES (Z)
# =========================================================

def ensure_admin_roles(admin_ids):
    connection = get_connection()
    for user_id in admin_ids:
        connection.execute(
            "INSERT OR IGNORE INTO admin_roles (user_id, role) VALUES (?, ?)",
            (user_id, "owner" if user_id == admin_ids[0] else "moderator"),
        )
    connection.commit()
    connection.close()


def get_admin_role(user_id: int) -> str:
    connection = get_connection()
    row = connection.execute("SELECT role FROM admin_roles WHERE user_id = ?", (user_id,)).fetchone()
    connection.close()
    return row["role"] if row else "moderator"


def is_admin_active(user_id: int) -> bool:
    """Return False immediately for fired/deactivated staff."""
    if int(user_id) not in {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}:
        return False
    con = get_connection()
    row = con.execute("SELECT status FROM employee_profiles WHERE admin_id=?", (int(user_id),)).fetchone()
    con.close()
    return not row or row["status"] != "fired"


def set_admin_role(user_id: int, role: str):
    connection = get_connection()
    connection.execute(
        "INSERT INTO admin_roles (user_id, role) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, updated_at=CURRENT_TIMESTAMP",
        (user_id, role),
    )
    connection.commit()
    connection.close()


def get_admin_roles():
    connection = get_connection()
    rows = connection.execute("SELECT user_id, role, created_at, updated_at FROM admin_roles ORDER BY user_id").fetchall()
    connection.close()
    return rows


# =========================================================
# SUPPORT
# =========================================================

def create_support_dialog(
    user_id: int,
    first_message: str,
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO support_dialogs (
            user_id,
            first_message,
            status,
            support_status,
            unread_admin
        )
        VALUES (
            ?,
            ?,
            'open',
            'new',
            1
        )
        """,
        (
            user_id,
            first_message,
        ),
    )

    dialog_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO support_messages (
            dialog_id,
            sender_id,
            sender_type,
            text
        )
        VALUES (?, ?, 'user', ?)
        """,
        (
            dialog_id,
            user_id,
            first_message,
        ),
    )

    connection.commit()
    connection.close()

    # Balance support workload immediately after creating the dialog.
    try:
        from ops import assign_workload
        assign_workload(dialog_id)
    except Exception as exc:
        print(f"⚠️ Workload assignment skipped for dialog {dialog_id}: {exc}")

    return dialog_id


def get_open_dialog_by_user(
    user_id: int,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM support_dialogs
        WHERE user_id = ?
          AND status = 'open'
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            user_id,
        ),
    ).fetchone()

    connection.close()

    return row


def get_dialog(
    dialog_id: int,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM support_dialogs
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    ).fetchone()

    connection.close()

    return row


def get_dialog_messages(
    dialog_id: int,
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM support_messages
        WHERE dialog_id = ?
        ORDER BY id ASC
        """,
        (
            dialog_id,
        ),
    ).fetchall()

    connection.close()

    return rows


def add_support_message(
    dialog_id: int,
    sender_id: int,
    sender_type: str,
    text: str,
):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO support_messages (
            dialog_id,
            sender_id,
            sender_type,
            text
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            dialog_id,
            sender_id,
            sender_type,
            text,
        ),
    )

    if sender_type == "user":

        connection.execute(
            """
            UPDATE support_dialogs
            SET
                unread_admin = unread_admin + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                dialog_id,
            ),
        )

    else:

        connection.execute(
            """
            UPDATE support_dialogs
            SET
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                dialog_id,
            ),
        )

    connection.commit()

    connection.close()


def get_open_dialogs():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            d.*,
            (
                SELECT text
                FROM support_messages
                WHERE dialog_id = d.id
                ORDER BY id DESC
                LIMIT 1
            ) AS last_message
        FROM support_dialogs d
        WHERE d.status = 'open'
        ORDER BY d.updated_at DESC
        """
    ).fetchall()

    connection.close()

    return rows


def assign_dialog(
    dialog_id: int,
    admin_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET
            assigned_admin_id = ?,
            support_status = 'in_progress',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            admin_id,
            dialog_id,
        ),
    )

    connection.commit()

    connection.close()


def unassign_dialog(
    dialog_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET
            assigned_admin_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    )

    connection.commit()

    connection.close()


def close_dialog(
    dialog_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET
            status = 'closed',
            support_status = 'closed',
            assigned_admin_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    )

    row = connection.execute("SELECT assigned_admin_id FROM support_dialogs WHERE id=?", (dialog_id,)).fetchone()
    connection.commit()
    connection.close()
    try:
        if row and row[0]:
            from ops import release_workload
            release_workload(int(row[0]))
    except Exception as exc:
        print(f"⚠️ Workload release skipped for dialog {dialog_id}: {exc}")


def mark_dialog_read_by_admin(
    dialog_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET unread_admin = 0
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    )

    connection.commit()

    connection.close()


def set_dialog_status(
    dialog_id: int,
    status: str,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET
            support_status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status,
            dialog_id,
        ),
    )

    connection.commit()

    connection.close()


def get_admin_control_message(dialog_id: int):
    connection = get_connection()
    row = connection.execute(
        """SELECT admin_control_chat_id, admin_control_message_id
           FROM support_dialogs WHERE id = ?""",
        (dialog_id,),
    ).fetchone()
    connection.close()
    return row


def set_admin_control_message(dialog_id: int, chat_id: int, message_id: int):
    connection = get_connection()
    connection.execute(
        """UPDATE support_dialogs
           SET admin_control_chat_id = ?,
               admin_control_message_id = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (chat_id, message_id, dialog_id),
    )
    connection.commit()
    connection.close()


def clear_admin_control_message(dialog_id: int):
    connection = get_connection()
    connection.execute(
        """UPDATE support_dialogs
           SET admin_control_chat_id = NULL,
               admin_control_message_id = NULL,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (dialog_id,),
    )
    connection.commit()
    connection.close()


def set_rejection_reason(story_id: int, reason: str):
    connection = get_connection()
    connection.execute(
        "UPDATE stories SET rejection_reason = ? WHERE id = ?",
        (reason, story_id),
    )
    connection.commit()
    connection.close()


def request_personal_contact(
    dialog_id: int,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT personal_contact_requested
        FROM support_dialogs
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    ).fetchone()

    if row is None:

        connection.close()

        return False

    if row["personal_contact_requested"]:

        connection.close()

        return False

    connection.execute(
        """
        UPDATE support_dialogs
        SET
            personal_contact_requested = 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    )

    connection.commit()

    connection.close()

    return True


# =========================================================
# COMPLAINTS / SUPPORT PRIORITY / SLA / MINI APP
# =========================================================

def create_complaint(story_id: int, user_id: int, reason: str):
    con = get_connection()
    cur = con.execute("""
        INSERT OR IGNORE INTO story_complaints(story_id,user_id,reason) VALUES(?,?,?)
    """, (story_id, user_id, reason.strip()[:500]))
    con.commit()
    row = con.execute("SELECT * FROM story_complaints WHERE story_id=? AND user_id=?", (story_id,user_id)).fetchone()
    con.close()
    return row


def get_complaints(status: str | None = None, limit: int = 100):
    con=get_connection()
    if status:
        rows=con.execute("SELECT * FROM story_complaints WHERE status=? ORDER BY created_at DESC LIMIT ?",(status,limit)).fetchall()
    else:
        rows=con.execute("SELECT * FROM story_complaints ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    con.close(); return rows


def update_complaint(complaint_id: int, status: str | None=None, priority: str | None=None, assigned_admin_id: int | None=None):
    con=get_connection(); fields=[]; vals=[]
    if status is not None: fields.append('status=?'); vals.append(status)
    if priority is not None: fields.append('priority=?'); vals.append(priority)
    if assigned_admin_id is not None: fields.append('assigned_admin_id=?'); vals.append(assigned_admin_id)
    fields.append('updated_at=CURRENT_TIMESTAMP')
    vals.append(complaint_id)
    con.execute(f"UPDATE story_complaints SET {', '.join(fields)} WHERE id=?", vals); con.commit(); con.close()


def save_story_version(story_id:int, changed_by:int, change_type:str):
    con=get_connection()
    row=con.execute('SELECT text, post_text FROM stories WHERE id=?',(story_id,)).fetchone()
    if not row: con.close(); return None
    n=con.execute('SELECT COALESCE(MAX(version_no),0)+1 FROM story_versions WHERE story_id=?',(story_id,)).fetchone()[0]
    con.execute('INSERT INTO story_versions(story_id,version_no,text,post_text,changed_by,change_type) VALUES(?,?,?,?,?,?)',(story_id,n,row['text'],row['post_text'],changed_by,change_type))
    con.commit(); out=con.execute('SELECT * FROM story_versions WHERE story_id=? AND version_no=?',(story_id,n)).fetchone(); con.close(); return out


def get_story_versions(story_id:int):
    con=get_connection(); rows=con.execute('SELECT * FROM story_versions WHERE story_id=? ORDER BY version_no DESC',(story_id,)).fetchall(); con.close(); return rows


def restore_story_version(version_id:int, admin_id:int):
    con=get_connection(); row=con.execute('SELECT * FROM story_versions WHERE id=?',(version_id,)).fetchone()
    if not row: con.close(); return None
    save_story_version(row['story_id'], admin_id, 'before_restore')
    con.execute('UPDATE stories SET text=?, post_text=? WHERE id=?',(row['text'],row['post_text'],row['story_id']))
    con.commit(); story=con.execute('SELECT * FROM stories WHERE id=?',(row['story_id'],)).fetchone(); con.close(); return story


def set_support_priority(dialog_id:int, priority:str):
    priority = priority if priority in {'critical','high','normal','low'} else 'normal'
    con=get_connection()
    con.execute("INSERT INTO support_sla(dialog_id,priority,first_response_due_at) VALUES(?,?,datetime('now',?)) ON CONFLICT(dialog_id) DO UPDATE SET priority=excluded.priority", (dialog_id,priority, {'critical':'+15 minutes','high':'+30 minutes','normal':'+2 hours','low':'+8 hours'}[priority]))
    con.commit(); con.close()


def get_support_priority(dialog_id:int):
    con=get_connection(); row=con.execute('SELECT * FROM support_sla WHERE dialog_id=?',(dialog_id,)).fetchone(); con.close(); return row


def get_sla_breaches():
    con=get_connection(); rows=con.execute("""SELECT d.*, COALESCE(s.priority,'normal') priority, s.first_response_due_at
      FROM support_dialogs d LEFT JOIN support_sla s ON s.dialog_id=d.id
      WHERE d.status='open' AND s.first_response_due_at IS NOT NULL AND datetime(s.first_response_due_at)<datetime('now')
      AND d.support_status='new' ORDER BY s.first_response_due_at ASC""").fetchall(); con.close(); return rows


def add_admin_notification(admin_id:int, kind:str, title:str, body:str):
    con=get_connection(); con.execute('INSERT INTO admin_notifications(admin_id,kind,title,body) VALUES(?,?,?,?)',(admin_id,kind,title,body)); con.commit(); con.close()


def get_admin_notifications(admin_id:int, unread_only:bool=False, limit:int=50):
    con=get_connection(); q='SELECT * FROM admin_notifications WHERE admin_id=?'
    params=[admin_id]
    if unread_only: q+=' AND read_at IS NULL'
    q+=' ORDER BY created_at DESC LIMIT ?'; params.append(limit)
    rows=con.execute(q,params).fetchall(); con.close(); return rows


def mark_admin_notification_read(notification_id:int, admin_id:int):
    con=get_connection(); con.execute('UPDATE admin_notifications SET read_at=CURRENT_TIMESTAMP WHERE id=? AND admin_id=?',(notification_id,admin_id)); con.commit(); con.close()


def get_moderator_metrics(days:int=30):
    con=get_connection(); rows=con.execute("""SELECT admin_id, action, COUNT(*) count FROM admin_audit_log WHERE created_at>=datetime('now',?) GROUP BY admin_id,action ORDER BY count DESC""",(f'-{days} days',)).fetchall(); con.close(); return rows


def get_top_stories(limit:int=10):
    con=get_connection(); rows=con.execute("""SELECT s.id,s.category,s.created_at,COUNT(r.id) reactions
      FROM stories s LEFT JOIN story_reactions r ON r.story_id=s.id
      WHERE s.status='published' GROUP BY s.id ORDER BY reactions DESC,s.id DESC LIMIT ?""",(limit,)).fetchall(); con.close(); return rows


def get_user_retention():
    con=get_connection(); rows=con.execute("""SELECT COUNT(*) total, SUM(CASE WHEN date(created_at)>=date('now','-1 day') THEN 1 ELSE 0 END) d1, SUM(CASE WHEN date(created_at)>=date('now','-7 day') THEN 1 ELSE 0 END) d7, SUM(CASE WHEN date(created_at)>=date('now','-30 day') THEN 1 ELSE 0 END) d30 FROM users""").fetchone(); con.close(); return rows


def update_story_content(story_id: int, text: str, post_text: str, admin_id: int):
    save_story_version(story_id, admin_id, 'edit')
    con = get_connection()
    con.execute('UPDATE stories SET text=?, post_text=? WHERE id=?', (text, post_text, story_id))
    con.commit(); row=con.execute('SELECT * FROM stories WHERE id=?',(story_id,)).fetchone(); con.close(); return row


def create_event_notification_once(admin_id:int, kind:str, title:str, body:str, fingerprint:str):
    con=get_connection()
    row=con.execute("SELECT id FROM admin_notifications WHERE admin_id=? AND kind=? AND body=? AND created_at>=datetime('now','-2 days') LIMIT 1",(admin_id,kind,fingerprint)).fetchone()
    if row:
        con.close(); return False
    con.execute('INSERT INTO admin_notifications(admin_id,kind,title,body) VALUES(?,?,?,?)',(admin_id,kind,title,body))
    con.commit(); con.close(); return True


# =========================================================
# BP / BR / BS / BT / BU / BW / BX / BY / BZ / CF / CH / CI
# =========================================================

def get_support_metrics():
    con=get_connection()
    row=con.execute("""
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open_count,
          AVG(CASE WHEN first_response_at IS NOT NULL
              THEN (julianday(first_response_at)-julianday(created_at))*86400 END) AS avg_first_response_seconds,
          AVG(CASE WHEN resolved_at IS NOT NULL
              THEN (julianday(resolved_at)-julianday(created_at))*86400 END) AS avg_resolution_seconds
        FROM support_dialogs
    """).fetchone()
    con.close(); return row


def get_support_queue():
    con=get_connection()
    rows=con.execute("""
      SELECT d.*, COALESCE(s.priority,'normal') AS priority,
        CASE WHEN d.assigned_admin_id IS NULL THEN 'unassigned' ELSE 'assigned' END AS assignment_status
      FROM support_dialogs d LEFT JOIN support_sla s ON s.dialog_id=d.id
      WHERE d.status='open' ORDER BY d.created_at ASC LIMIT 200
    """).fetchall(); con.close(); return rows


def get_category_stats():
    con=get_connection(); rows=con.execute("""
      SELECT COALESCE(NULLIF(category,''),'Без категории') category,
             COUNT(*) stories,
             SUM(CASE WHEN status='published' THEN 1 ELSE 0 END) published
      FROM stories GROUP BY COALESCE(NULLIF(category,''),'Без категории')
      ORDER BY stories DESC
    """).fetchall(); con.close(); return rows


def get_publication_hour_stats():
    con=get_connection(); rows=con.execute("""
      SELECT CAST(strftime('%H', created_at) AS INTEGER) hour, COUNT(*) count
      FROM stories WHERE status='published' AND channel_message_id IS NOT NULL
      GROUP BY hour ORDER BY hour
    """).fetchall(); con.close(); return rows


def get_funnel_stats():
    con=get_connection()
    users=con.execute('SELECT COUNT(*) c FROM users').fetchone()['c']
    stories=con.execute('SELECT COUNT(*) c FROM stories').fetchone()['c']
    published=con.execute("SELECT COUNT(*) c FROM stories WHERE status='published'").fetchone()['c']
    support=con.execute('SELECT COUNT(DISTINCT user_id) c FROM support_dialogs').fetchone()['c']
    con.close(); return {'users':users,'stories':stories,'published':published,'support_users':support}


def get_security_events(limit=300):
    con=get_connection(); rows=con.execute("""
      SELECT id,admin_id,action,story_id,dialog_id,user_id,details,created_at
      FROM admin_audit_log ORDER BY id DESC LIMIT ?
    """,(limit,)).fetchall(); con.close(); return rows


def get_publication_queue():
    con=get_connection(); rows=con.execute("""
      SELECT id,user_id,status,scheduled_at,scheduled_by,post_text,created_at
      FROM stories WHERE scheduled_at IS NOT NULL AND status IN ('waiting','scheduled','publishing')
      ORDER BY scheduled_at ASC LIMIT 200
    """).fetchall(); con.close(); return rows


def auto_plan_stories(story_ids, start_at_utc, interval_minutes, admin_id):
    from datetime import datetime, timedelta
    current=datetime.fromisoformat(start_at_utc.replace('Z','+00:00'))
    if current.tzinfo is None:
        from zoneinfo import ZoneInfo
        current=current.replace(tzinfo=ZoneInfo('UTC'))
    result=[]
    con=get_connection()
    for sid in story_ids:
        con.execute("UPDATE stories SET scheduled_at=?, scheduled_by=? WHERE id=? AND status='waiting'",
                    (current.isoformat(),admin_id,sid))
        result.append({'id':sid,'scheduled_at':current.isoformat()})
        current += timedelta(minutes=interval_minutes)
    con.commit(); con.close(); return result


def create_repost_job(story_id, scheduled_at_utc, admin_id):
    con=get_connection()
    cur=con.execute('INSERT INTO repost_jobs(story_id,scheduled_at,admin_id) VALUES(?,?,?)',(story_id,scheduled_at_utc,admin_id))
    con.commit(); job_id=cur.lastrowid; con.close(); return job_id


def get_repost_jobs(limit=100):
    con=get_connection()
    rows=con.execute('SELECT * FROM repost_jobs ORDER BY scheduled_at LIMIT ?',(limit,)).fetchall(); con.close(); return rows


def get_due_repost_jobs(now_utc, limit=10):
    con=get_connection(); rows=con.execute("SELECT * FROM repost_jobs WHERE status='scheduled' AND scheduled_at<=? ORDER BY scheduled_at LIMIT ?",(now_utc,limit)).fetchall(); con.close(); return rows

def claim_repost_job(job_id):
    con=get_connection(); cur=con.execute("UPDATE repost_jobs SET status='publishing' WHERE id=? AND status='scheduled'",(job_id,)); con.commit(); ok=cur.rowcount==1; con.close(); return ok

def finish_repost_job(job_id,status='published'):
    con=get_connection(); con.execute("UPDATE repost_jobs SET status=? WHERE id=?",(status,job_id)); con.commit(); con.close()

# =========================================================
# PLATFORM SETTINGS / EMPLOYEES / MONITORING
# =========================================================

def _ensure_platform_tables(con):
    # Tables are created and changed only by Alembic migrations.
    return None


def ensure_platform_defaults():
    con = get_connection()
    _ensure_platform_tables(con)
    defaults = {
        'ai_model': os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b'),
        'ai_fallback_model': os.getenv('GROQ_FALLBACK_MODEL', 'openai/gpt-oss-20b'),
        'ai_safety_model': os.getenv('GROQ_SAFETY_MODEL', 'openai/gpt-oss-safeguard-20b'),
        'ai_temperature': '0.2',
        'ai_max_tokens': '1800',
        'support_notification_enabled': '1',
        'auto_backup_enabled': '1',
        'auto_reports_enabled': '1',
        'maintenance_enabled': '1',
        'story_lock_minutes': '20',
    }
    for key, value in defaults.items():
        con.execute('INSERT OR IGNORE INTO app_settings(key,value) VALUES(?,?)', (key, value))
    for key in ('analysis', 'moderation', 'quality', 'structured_moderation'):
        con.execute('INSERT OR IGNORE INTO ai_checks(key,enabled) VALUES(?,1)', (key,))
    admin_ids = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    for admin_id in admin_ids:
        con.execute(
            """
            INSERT INTO employee_profiles(admin_id,position,status,work_started_at)
            VALUES(?, 'moderator', 'employee', CURRENT_TIMESTAMP)
            ON CONFLICT(admin_id) DO NOTHING
            """,
            (admin_id,),
        )

    # Keep the DB registry aligned with the models explicitly configured in Railway.
    configured_models = [x.strip() for x in os.getenv('GROQ_MODELS', '').split(',') if x.strip()]
    primary = os.getenv('GROQ_MODEL', '').strip()
    fallback = os.getenv('GROQ_FALLBACK_MODEL', '').strip()
    safety = os.getenv('GROQ_SAFETY_MODEL', '').strip()
    ordered = []
    for model in [primary, fallback, *configured_models, safety]:
        if model and model not in ordered:
            ordered.append(model)
    for idx, model in enumerate(ordered):
        enabled = model != safety or bool(safety)
        con.execute(
            """
            INSERT INTO ai_model_configs(model,enabled,priority,max_tokens,temperature)
            VALUES(?,?,?,?,?)
            ON CONFLICT(model) DO NOTHING
            """,
            (model, enabled, 10 + idx * 10, 1800 if idx else 2200, 0.0 if model == safety else 0.2),
        )
    # Do not silently disable user-selected models. Only migrate legacy defaults.
    if primary:
        con.execute("UPDATE app_settings SET value=? WHERE key='ai_model' AND value IN ('openai/gpt-oss-120b','llama-3.3-70b-versatile','llama-3.1-8b-instant')", (primary,))
    if fallback:
        con.execute("UPDATE app_settings SET value=? WHERE key='ai_fallback_model' AND value IN ('openai/gpt-oss-20b','llama-3.1-8b-instant','llama-3.3-70b-versatile')", (fallback,))
    # Disable only legacy defaults from older versions; never delete user data.
    con.execute("UPDATE ai_model_configs SET enabled=false WHERE model IN ('openai/gpt-oss-120b','openai/gpt-oss-20b','openai/gpt-oss-safeguard-20b') AND model NOT IN (%s,%s,%s)", (primary or '__none__', fallback or '__none__', safety or '__none__'))
    con.commit(); con.close()


def get_setting(key, default=None):
    con=get_connection(); _ensure_platform_tables(con)
    row=con.execute('SELECT value FROM app_settings WHERE key=?',(key,)).fetchone(); con.close()
    return row['value'] if row else default


def set_setting(key, value, admin_id=None):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT INTO app_settings(key,value,updated_by,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) '
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP',
                (key, str(value), admin_id))
    con.commit(); con.close()


def get_all_settings():
    con=get_connection(); _ensure_platform_tables(con)
    rows=con.execute('SELECT * FROM app_settings ORDER BY key').fetchall(); con.close(); return rows


def get_ai_checks():
    con=get_connection(); _ensure_platform_tables(con)
    rows=con.execute('SELECT * FROM ai_checks ORDER BY key').fetchall(); con.close(); return rows


def set_ai_check(key, enabled, admin_id=None):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT INTO ai_checks(key,enabled,updated_by,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) '
                'ON CONFLICT(key) DO UPDATE SET enabled=excluded.enabled,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP',
                (key, 1 if enabled else 0, admin_id)); con.commit(); con.close()


def ai_check_enabled(key):
    con=get_connection(); _ensure_platform_tables(con)
    row=con.execute('SELECT enabled FROM ai_checks WHERE key=?',(key,)).fetchone(); con.close()
    return bool(row['enabled']) if row else True


def lock_story(story_id, admin_id, minutes=20):
    from datetime import datetime, timedelta
    con=get_connection(); _ensure_platform_tables(con)
    now=datetime.utcnow(); expires=now+timedelta(minutes=minutes)
    con.execute('DELETE FROM story_locks WHERE expires_at<=CURRENT_TIMESTAMP')
    row=con.execute('SELECT * FROM story_locks WHERE story_id=?',(story_id,)).fetchone()
    if row and int(row['admin_id']) != int(admin_id):
        con.close(); return row
    con.execute('INSERT INTO story_locks(story_id,admin_id,locked_at,expires_at) VALUES(?,?,?,?) '
                'ON CONFLICT(story_id) DO UPDATE SET admin_id=excluded.admin_id,locked_at=excluded.locked_at,expires_at=excluded.expires_at',
                (story_id,admin_id,now.isoformat(),expires.isoformat()))
    con.commit(); row=con.execute('SELECT * FROM story_locks WHERE story_id=?',(story_id,)).fetchone(); con.close(); return row


def get_story_lock(story_id):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('DELETE FROM story_locks WHERE expires_at<=CURRENT_TIMESTAMP')
    row=con.execute('SELECT * FROM story_locks WHERE story_id=?',(story_id,)).fetchone(); con.commit(); con.close(); return row


def unlock_story(story_id, admin_id=None):
    con=get_connection(); _ensure_platform_tables(con)
    if admin_id is None: con.execute('DELETE FROM story_locks WHERE story_id=?',(story_id,))
    else: con.execute('DELETE FROM story_locks WHERE story_id=? AND admin_id=?',(story_id,admin_id))
    con.commit(); con.close()


def log_system_error(service, message, details='', level='error'):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT INTO system_errors(service,level,message,details) VALUES(?,?,?,?)',(service,level,str(message),str(details)))
    con.commit(); con.close()


def get_system_errors(limit=200):
    con=get_connection(); _ensure_platform_tables(con)
    rows=con.execute('SELECT * FROM system_errors ORDER BY id DESC LIMIT ?',(limit,)).fetchall(); con.close(); return rows


def set_system_health(service, status, details=''):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT INTO system_health(service,status,details,checked_at) VALUES(?,?,?,CURRENT_TIMESTAMP) '
                'ON CONFLICT(service) DO UPDATE SET status=excluded.status,details=excluded.details,checked_at=CURRENT_TIMESTAMP',
                (service,status,str(details))); con.commit(); con.close()


def get_system_health():
    con=get_connection(); _ensure_platform_tables(con)
    rows=con.execute('SELECT * FROM system_health ORDER BY service').fetchall(); con.close(); return rows


def create_ai_priority(story_id, priority='normal', reason=''):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT INTO ai_priority_queue(story_id,priority,reason) VALUES(?,?,?)',(story_id,priority,reason)); con.commit(); con.close()


def get_ai_priority_queue(limit=100):
    con=get_connection(); _ensure_platform_tables(con)
    rows=con.execute("SELECT * FROM ai_priority_queue WHERE status='queued' ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, id LIMIT ?",(limit,)).fetchall(); con.close(); return rows


def assign_training(admin_id, course, lesson, due_at=None):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT INTO employee_training(admin_id,course,lesson,due_at) VALUES(?,?,?,?)',(admin_id,course,lesson,due_at)); con.commit(); con.close()


def get_training(admin_id=None, limit=200):
    con=get_connection(); _ensure_platform_tables(con)
    if admin_id is None: rows=con.execute('SELECT * FROM employee_training ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall()
    else: rows=con.execute('SELECT * FROM employee_training WHERE admin_id=? ORDER BY created_at DESC LIMIT ?',(admin_id,limit)).fetchall()
    con.close(); return rows


def set_training_status(training_id, status, score=None):
    con=get_connection(); _ensure_platform_tables(con)
    completed=', completed_at=CURRENT_TIMESTAMP' if status=='completed' else ''
    con.execute(f'UPDATE employee_training SET status=?,score=?{completed} WHERE id=?',(status,score,training_id)); con.commit(); con.close()


def set_moderator_goal(admin_id, period, publish=0, moderate=0, response=0):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT INTO moderator_goals(admin_id,period,target_publish,target_moderate,target_response) VALUES(?,?,?,?,?) '
                'ON CONFLICT(admin_id,period) DO UPDATE SET target_publish=excluded.target_publish,target_moderate=excluded.target_moderate,target_response=excluded.target_response',
                (admin_id,period,publish,moderate,response)); con.commit(); con.close()


def get_moderator_goals(period=None):
    con=get_connection(); _ensure_platform_tables(con)
    if period: rows=con.execute('SELECT * FROM moderator_goals WHERE period=?',(period,)).fetchall()
    else: rows=con.execute('SELECT * FROM moderator_goals ORDER BY period DESC,admin_id').fetchall()
    con.close(); return rows


def record_kpi_event(admin_id, action, seconds=0, dangerous=False, correction=False):
    """Increment the real daily KPI counters from actual moderation events."""
    con = get_connection()
    row = con.execute(
        "SELECT id FROM moderator_kpi_daily WHERE admin_id=? AND day=(CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date",
        (int(admin_id),),
    ).fetchone()
    if not row:
        con.execute(
            "INSERT INTO moderator_kpi_daily(admin_id,day) VALUES(?,(CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date)",
            (int(admin_id),),
        )
    moderated = 1 if action in {"publish", "reject", "edit", "moderate"} else 0
    published = 1 if action == "publish" else 0
    errors = 1 if action == "error" else 0
    support = 1 if action == "support_response" else 0
    con.execute(
        """
        UPDATE moderator_kpi_daily
        SET moderated=COALESCE(moderated,0)+?,
            published=COALESCE(published,0)+?,
            errors=COALESCE(errors,0)+?,
            dangerous=COALESCE(dangerous,0)+?,
            support_responses=COALESCE(support_responses,0)+?,
            response_seconds=COALESCE(response_seconds,0)+?,
            moderation_seconds=COALESCE(moderation_seconds,0)+?,
            post_corrections=COALESCE(post_corrections,0)+?
        WHERE admin_id=? AND day=(CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date
        """,
        (
            moderated, published, errors, 1 if dangerous else 0, support,
            int(seconds if support else 0), int(seconds if moderated else 0),
            1 if correction else 0, int(admin_id),
        ),
    )
    con.commit()
    con.close()


def get_moderator_performance(days=30):
    con=get_connection(); _ensure_platform_tables(con)
    rows=con.execute("""
      SELECT admin_id,
      SUM(CASE WHEN action LIKE '%publish%' THEN 1 ELSE 0 END) published,
      SUM(CASE WHEN action LIKE '%edit%' OR action LIKE '%moderate%' THEN 1 ELSE 0 END) moderated,
      COUNT(*) actions
      FROM admin_audit_log
      WHERE created_at>=datetime('now',?) GROUP BY admin_id ORDER BY published DESC,moderated DESC,actions DESC
    """,(f'-{days} days',)).fetchall(); con.close(); return rows


def integrity_check():
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('SELECT 1').fetchone()
    result = 'ok'
    foreign = []
    con.close(); return {'integrity_check': result, 'foreign_key_errors': len(foreign), 'ok': result=='ok' and not foreign}


def report_was_sent(report_type, period_key):
    con=get_connection(); _ensure_platform_tables(con)
    row=con.execute('SELECT id FROM report_log WHERE report_type=? AND period_key=?',(report_type,period_key)).fetchone(); con.close(); return bool(row)


def mark_report_sent(report_type, period_key):
    con=get_connection(); _ensure_platform_tables(con)
    con.execute('INSERT OR IGNORE INTO report_log(report_type,period_key) VALUES(?,?)',(report_type,period_key)); con.commit(); con.close()


# =========================================================
# FOUNDER / AI CONTROL / LMS V2
# =========================================================

def get_ai_model_configs():
    con = get_connection()
    rows = con.execute(
        "SELECT * FROM ai_model_configs ORDER BY priority ASC, model ASC"
    ).fetchall()
    con.close()
    return rows


def set_ai_model_config(model, enabled=True, priority=100, max_tokens=1800, temperature=0.2, admin_id=None):
    con = get_connection()
    con.execute(
        """
        INSERT INTO ai_model_configs(model,enabled,priority,max_tokens,temperature,updated_by,updated_at)
        VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(model) DO UPDATE SET
          enabled=excluded.enabled,
          priority=excluded.priority,
          max_tokens=excluded.max_tokens,
          temperature=excluded.temperature,
          updated_by=excluded.updated_by,
          updated_at=CURRENT_TIMESTAMP
        """,
        (model, bool(enabled), int(priority), int(max_tokens), float(temperature), admin_id),
    )
    con.commit()
    con.close()


def get_ai_model_health(limit=100):
    con = get_connection()
    rows = con.execute(
        "SELECT * FROM ai_model_health ORDER BY checked_at DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    con.close()
    return rows


def set_ai_model_health(model, status, latency_ms=0, error_rate=0, details="", checked_at=None):
    con = get_connection()
    con.execute(
        """
        INSERT INTO ai_model_health(model,status,latency_ms,error_rate,details,checked_at)
        VALUES(?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))
        ON CONFLICT(model) DO UPDATE SET
          status=excluded.status,
          latency_ms=excluded.latency_ms,
          error_rate=excluded.error_rate,
          details=excluded.details,
          checked_at=excluded.checked_at
        """,
        (model, status, int(latency_ms or 0), float(error_rate or 0), str(details), checked_at),
    )
    con.commit()
    con.close()


def log_ai_safety_event(story_id, stage, model, passed, risk_score=None, confidence=None, flags=None, details=""):
    con = get_connection()
    con.execute(
        """
        INSERT INTO ai_safety_events
          (story_id,stage,model,passed,risk_score,confidence,flags,details)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            story_id,
            stage,
            model,
            bool(passed),
            risk_score,
            confidence,
            json.dumps(flags or [], ensure_ascii=False),
            str(details),
        ),
    )
    con.commit()
    con.close()


def get_latest_safety_decision(story_id):
    con = get_connection()
    try:
        row = con.execute(
            "SELECT * FROM ai_safety_events WHERE story_id=? ORDER BY created_at DESC LIMIT 1",
            (int(story_id),),
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row['details'] or '{}')
        except Exception:
            payload = {}
        return {
            'recommendation': payload.get('recommendation', 'manual_review'),
            'risk_score': float(payload.get('risk_score', row['risk_score'] or 0.5) or 0.5),
            'details': payload,
            'stage': row['stage'],
            'created_at': row['created_at'],
        }
    finally:
        con.close()



def get_ai_safety_events(story_id=None, limit=200):
    con = get_connection()
    if story_id is None:
        rows = con.execute(
            "SELECT * FROM ai_safety_events ORDER BY created_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM ai_safety_events WHERE story_id=? ORDER BY created_at DESC LIMIT ?",
            (int(story_id), int(limit)),
        ).fetchall()
    con.close()
    return rows


def create_deployment_event(environment, status, commit_sha="", details=""):
    con = get_connection()
    con.execute(
        "INSERT INTO deploy_events(environment,status,commit_sha,details) VALUES(?,?,?,?)",
        (environment, status, commit_sha, details),
    )
    con.commit()
    con.close()


def get_deployment_events(limit=100):
    con = get_connection()
    rows = con.execute(
        "SELECT * FROM deploy_events ORDER BY created_at DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    con.close()
    return rows


def founder_dashboard():
    con = get_connection()
    try:
        stats = con.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM users) AS users,
              (SELECT COUNT(*) FROM stories) AS stories,
              (SELECT COUNT(*) FROM stories WHERE status='waiting') AS waiting,
              (SELECT COUNT(*) FROM stories WHERE status='published') AS published,
              (SELECT COUNT(*) FROM stories WHERE status='rejected') AS rejected,
              (SELECT COUNT(*) FROM support_dialogs WHERE status='open') AS open_support,
              (SELECT COUNT(*) FROM ai_priority_queue WHERE status='queued') AS ai_queue
            """
        ).fetchone()
        hourly = con.execute(
            """
            SELECT EXTRACT(HOUR FROM created_at)::int AS hour, COUNT(*)::int AS count
            FROM stories
            WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        publications = con.execute(
            """
            SELECT (created_at AT TIME ZONE 'Europe/Moscow')::date AS day,
                   COUNT(*)::int AS count
            FROM stories
            WHERE status='published'
              AND created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        users = con.execute(
            """
            SELECT (created_at AT TIME ZONE 'Europe/Moscow')::date AS day,
                   COUNT(*)::int AS count
            FROM users
            WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        active_mods = con.execute(
            """
            SELECT COUNT(*)::int AS count
            FROM employee_profiles
            WHERE status <> 'fired'
            """
        ).fetchone()
        avg_wait = con.execute(
            """
            SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (COALESCE(first_response_at,CURRENT_TIMESTAMP)-created_at))),0) AS seconds
            FROM support_dialogs WHERE status <> 'new'
            """
        ).fetchone()
        return {
            "stats": dict(stats) if stats else {},
            "hourly_load": [dict(r) for r in hourly],
            "publications": [dict(r) for r in publications],
            "users": [dict(r) for r in users],
            "active_moderators": int(active_mods["count"] if active_mods else 0),
            "average_wait_seconds": float(avg_wait["seconds"] if avg_wait else 0),
        }
    finally:
        con.close()


def submit_lms_test(assignment_id, answers, admin_id):
    """Auto-check all questions belonging to the assigned course."""
    con = get_connection()
    assignment = con.execute(
        """
        SELECT a.*, c.title AS course_title
        FROM lms_assignments a JOIN lms_courses c ON c.id=a.course_id
        WHERE a.id=? AND a.admin_id=?
        """,
        (int(assignment_id), int(admin_id)),
    ).fetchone()
    if not assignment:
        con.close()
        raise ValueError("Обучение не найдено.")

    questions = con.execute(
        """
        SELECT t.id,t.question,t.options,t.correct_answer,t.points
        FROM lms_tests t
        JOIN lms_lessons l ON l.id=t.lesson_id
        WHERE l.course_id=?
        ORDER BY l.position,t.id
        """,
        (assignment["course_id"],),
    ).fetchall()

    answers = answers or {}
    total = sum(int(q["points"] or 1) for q in questions) or 1
    score_points = 0
    for q in questions:
        given = str(answers.get(str(q["id"]), answers.get(q["id"], ""))).strip()
        if given == str(q["correct_answer"] or "").strip():
            score_points += int(q["points"] or 1)
    score = round(score_points / total * 100, 2)
    passed = score >= 70
    con.execute(
        "INSERT INTO lms_attempts(assignment_id,score,passed,answers) VALUES(?,?,?,?)",
        (int(assignment_id), score, passed, json.dumps(answers, ensure_ascii=False)),
    )
    con.execute(
        """
        UPDATE lms_assignments
        SET progress=CASE WHEN ? THEN 100 ELSE GREATEST(progress,50) END,
            status=CASE WHEN ? THEN 'completed' ELSE 'in_progress' END,
            completed_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
        WHERE id=?
        """,
        (passed, passed, passed, int(assignment_id)),
    )
    con.commit()
    con.close()
    return {"score": score, "passed": passed, "total_questions": len(questions)}


def get_kpi_dashboard(days=30):
    con = get_connection()
    try:
        days = max(1, min(int(days), 365))
        daily = con.execute(
            """
            SELECT day,
                   COALESCE(SUM(moderated),0) AS moderated,
                   COALESCE(SUM(published),0) AS published,
                   COALESCE(SUM(errors),0) AS errors,
                   COALESCE(SUM(dangerous),0) AS dangerous,
                   COALESCE(SUM(support_responses),0) AS support_responses,
                   COALESCE(SUM(response_seconds),0) AS response_seconds,
                   COALESCE(SUM(moderation_seconds),0) AS moderation_seconds,
                   COALESCE(SUM(post_corrections),0) AS post_corrections
            FROM moderator_kpi_daily
            WHERE day >= (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - (?::int)
            GROUP BY day ORDER BY day
            """, (days - 1,),
        ).fetchall()
        rows = con.execute(
            """
            SELECT admin_id,
                   COALESCE(SUM(moderated),0) AS moderated,
                   COALESCE(SUM(published),0) AS published,
                   COALESCE(SUM(errors),0) AS errors,
                   COALESCE(SUM(dangerous),0) AS dangerous,
                   COALESCE(SUM(support_responses),0) AS support_responses,
                   COALESCE(SUM(response_seconds),0) AS response_seconds,
                   COALESCE(SUM(moderation_seconds),0) AS moderation_seconds,
                   COALESCE(SUM(post_corrections),0) AS post_corrections
            FROM moderator_kpi_daily
            WHERE day >= (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Moscow')::date - (?::int)
            GROUP BY admin_id
            """, (days - 1,),
        ).fetchall()
        ranking=[]
        for r in rows:
            moderated=float(r['moderated'] or 0); published=float(r['published'] or 0)
            errors=float(r['errors'] or 0); dangerous=float(r['dangerous'] or 0)
            corrections=float(r['post_corrections'] or 0)
            avg_mod=(float(r['moderation_seconds'] or 0)/moderated) if moderated else 0
            quality=max(0.0, 100.0 - errors/max(moderated,1)*100.0 - dangerous/max(moderated,1)*35.0 - corrections/max(published,1)*25.0)
            speed=max(0.0, 100.0 - min(100.0, avg_mod/600.0*100.0)) if moderated else 50.0
            volume=min(100.0, published*5.0 + moderated*1.0)
            score=round(quality*0.60 + speed*0.20 + volume*0.20, 2)
            ranking.append({**dict(r), 'avg_moderation_seconds': round(avg_mod,1), 'quality': round(quality,2), 'speed': round(speed,2), 'score': score})
        ranking.sort(key=lambda x:(-x['score'], -int(x['published'] or 0)))
        return {'days': days, 'daily':[dict(r) for r in daily], 'ranking':ranking}
    finally:
        con.close()



def get_lms_full():
    con = get_connection()
    try:
        courses = con.execute("SELECT * FROM lms_courses ORDER BY id").fetchall()
        lessons = con.execute("SELECT * FROM lms_lessons ORDER BY course_id,position,id").fetchall()
        tests = con.execute("SELECT * FROM lms_tests ORDER BY lesson_id,id").fetchall()
        tasks = con.execute("SELECT * FROM lms_practical_tasks ORDER BY course_id,id").fetchall()
        exams = con.execute("SELECT * FROM lms_exams ORDER BY course_id,id").fetchall()
        assignments = con.execute("SELECT a.*, c.title AS course_title FROM lms_assignments a JOIN lms_courses c ON c.id=a.course_id ORDER BY a.id DESC LIMIT 500").fetchall()
        return {
            "courses": [dict(x) for x in courses],
            "lessons": [dict(x) for x in lessons],
            "tests": [dict(x) for x in tests],
            "practical_tasks": [dict(x) for x in tasks],
            "exams": [dict(x) for x in exams],
            "assignments": [dict(x) for x in assignments],
        }
    finally:
        con.close()
