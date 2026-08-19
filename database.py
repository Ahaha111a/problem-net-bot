import os
import sqlite3
from pathlib import Path


DB_PATH = Path(
    os.getenv("DB_PATH", "bot.db")
)


if DB_PATH.parent and str(DB_PATH.parent) != ".":
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


def get_connection():
    connection = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    connection = get_connection()

    cursor = connection.cursor()

    # =====================================================
    # STORIES
    # =====================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            ai_result TEXT,
            post_text TEXT,
            status TEXT DEFAULT 'waiting',
            rejection_reason TEXT,
            channel_message_id INTEGER,
            ai_moderation_result TEXT,
            category TEXT,
            scheduled_at TIMESTAMP,
            scheduled_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # =====================================================
    # SUPPORT DIALOGS
    # =====================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS support_dialogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            first_message TEXT,
            status TEXT DEFAULT 'open',
            support_status TEXT DEFAULT 'new',
            assigned_admin_id INTEGER,
            unread_admin INTEGER DEFAULT 0,
            personal_contact_requested INTEGER DEFAULT 0,
            admin_control_chat_id INTEGER,
            admin_control_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # =====================================================
    # SUPPORT MESSAGES
    # =====================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dialog_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(dialog_id)
                REFERENCES support_dialogs(id)
        )
        """
    )

    # =====================================================
    # USERS
    #
    # Здесь храним расписание ежедневного уведомления
    # об экстренной поддержке.
    # =====================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            notification_date TEXT,
            notification_minute INTEGER,
            notification_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # =====================================================
    # REACTIONS
    # =====================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS story_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reaction TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(story_id, user_id),
            FOREIGN KEY(story_id) REFERENCES stories(id)
        )
        """
    )

    # =====================================================
    # ADMIN AUDIT LOG
    # =====================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            story_id INTEGER,
            dialog_id INTEGER,
            user_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # =====================================================
    # ADMIN ROLES (Z)
    # =====================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_roles (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'moderator',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


    # =====================================================
    # MODERATION / SUPPORT EXTENSIONS (AB, AJ, AK, AL, AN, AO-AR)
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS story_complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'new',
            priority TEXT DEFAULT 'normal',
            assigned_admin_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(story_id, user_id),
            FOREIGN KEY(story_id) REFERENCES stories(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS story_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            version_no INTEGER NOT NULL,
            text TEXT,
            post_text TEXT,
            changed_by INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(story_id) REFERENCES stories(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            read_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_sla (
            dialog_id INTEGER PRIMARY KEY,
            priority TEXT DEFAULT 'normal',
            first_response_due_at TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY(dialog_id) REFERENCES support_dialogs(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS moderator_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # =====================================================
    # SOFT MIGRATIONS
    # =====================================================

    migrations = {

        "stories": {
            "ai_result": "TEXT",
            "post_text": "TEXT",
            "status": "TEXT DEFAULT 'waiting'",
            "created_at": "TIMESTAMP",
            "rejection_reason": "TEXT",
            "channel_message_id": "INTEGER",
            "ai_moderation_result": "TEXT",
            "category": "TEXT",
            "scheduled_at": "TIMESTAMP",
            "scheduled_by": "INTEGER",
        },

        "support_dialogs": {
            "first_message": "TEXT",
            "status": "TEXT DEFAULT 'open'",
            "support_status": "TEXT DEFAULT 'new'",
            "assigned_admin_id": "INTEGER",
            "unread_admin": "INTEGER DEFAULT 0",
            "personal_contact_requested": "INTEGER DEFAULT 0",
            "admin_control_chat_id": "INTEGER",
            "admin_control_message_id": "INTEGER",
            "first_response_at": "TIMESTAMP",
            "resolved_at": "TIMESTAMP",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP",
        },

        "users": {
            "notification_date": "TEXT",
            "notification_minute": "INTEGER",
            "notification_at": "TEXT",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },


        "admin_roles": {
            "role": "TEXT DEFAULT 'moderator'",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
    }

    for table, columns in migrations.items():

        existing = {
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        for column, definition in columns.items():

            if column not in existing:

                connection.execute(
                    f"""
                    ALTER TABLE {table}
                    ADD COLUMN {column} {definition}
                    """
                )

    # Регистрируем пользователей, которые появились до введения таблицы users.
    connection.execute(
        """
        INSERT OR IGNORE INTO users (user_id, notification_date, notification_minute)
        SELECT DISTINCT user_id, NULL, NULL FROM stories
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO users (user_id, notification_date, notification_minute)
        SELECT DISTINCT user_id, NULL, NULL FROM support_dialogs
        """
    )

    # Инициализируем роли из ADMIN_IDS, не меняя существующие роли.
    try:
        admin_ids = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
        for admin_id in admin_ids:
            connection.execute(
                "INSERT OR IGNORE INTO admin_roles (user_id, role) VALUES (?, ?)",
                (admin_id, "owner" if admin_id == admin_ids[0] else "moderator"),
            )
    except Exception:
        pass

    connection.commit()

    connection.close()


# =========================================================
# USERS
# =========================================================

def _random_next_notification_iso():
    import random
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Oslo"))
    # Случайное время примерно раз в 24 часа: от 23 до 25 часов после предыдущего.
    seconds = random.randint(23 * 3600, 25 * 3600)
    return (now + timedelta(seconds=seconds)).isoformat()


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
    from datetime import datetime
    import shutil

    target_dir = Path(backup_dir or os.getenv('BACKUP_DIR', '') or '/app/data/backups')
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    target = target_dir / f'bot_{stamp}.db'

    source = get_connection()
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    # Keep latest 14 backups.
    backups = sorted(target_dir.glob('bot_*.db'), key=lambda x: x.stat().st_mtime, reverse=True)
    for old in backups[14:]:
        try:
            old.unlink()
        except OSError:
            pass
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

    connection.commit()

    connection.close()


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
    con.execute("""CREATE TABLE IF NOT EXISTS repost_jobs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, story_id INTEGER NOT NULL,
      scheduled_at TEXT NOT NULL, admin_id INTEGER NOT NULL,
      status TEXT DEFAULT 'scheduled', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur=con.execute('INSERT INTO repost_jobs(story_id,scheduled_at,admin_id) VALUES(?,?,?)',(story_id,scheduled_at_utc,admin_id))
    con.commit(); job_id=cur.lastrowid; con.close(); return job_id


def get_repost_jobs(limit=100):
    con=get_connection()
    con.execute("""CREATE TABLE IF NOT EXISTS repost_jobs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, story_id INTEGER NOT NULL,
      scheduled_at TEXT NOT NULL, admin_id INTEGER NOT NULL,
      status TEXT DEFAULT 'scheduled', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    rows=con.execute('SELECT * FROM repost_jobs ORDER BY scheduled_at LIMIT ?',(limit,)).fetchall(); con.close(); return rows


def get_due_repost_jobs(now_utc, limit=10):
    con=get_connection(); con.execute("""CREATE TABLE IF NOT EXISTS repost_jobs(
      id INTEGER PRIMARY KEY AUTOINCREMENT, story_id INTEGER NOT NULL,
      scheduled_at TEXT NOT NULL, admin_id INTEGER NOT NULL,
      status TEXT DEFAULT 'scheduled', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""); rows=con.execute("SELECT * FROM repost_jobs WHERE status='scheduled' AND scheduled_at<=? ORDER BY scheduled_at LIMIT ?",(now_utc,limit)).fetchall(); con.close(); return rows

def claim_repost_job(job_id):
    con=get_connection(); cur=con.execute("UPDATE repost_jobs SET status='publishing' WHERE id=? AND status='scheduled'",(job_id,)); con.commit(); ok=cur.rowcount==1; con.close(); return ok

def finish_repost_job(job_id,status='published'):
    con=get_connection(); con.execute("UPDATE repost_jobs SET status=? WHERE id=?",(status,job_id)); con.commit(); con.close()
