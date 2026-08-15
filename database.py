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
            priority INTEGER DEFAULT 1,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS support_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dialog_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(dialog_id) REFERENCES support_dialogs(id)
        )
        """
    )

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
        },

        "support_dialogs": {
            "first_message": "TEXT",
            "status": "TEXT DEFAULT 'open'",
            "support_status": "TEXT DEFAULT 'new'",
            "assigned_admin_id": "INTEGER",
            "unread_admin": "INTEGER DEFAULT 0",
            "personal_contact_requested": "INTEGER DEFAULT 0",
            "priority": "INTEGER DEFAULT 1",
            "admin_control_chat_id": "INTEGER",
            "admin_control_message_id": "INTEGER",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP",
        },

        "users": {
            "notification_date": "TEXT",
            "notification_minute": "INTEGER",
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

    connection.commit()

    connection.close()


# =========================================================
# USERS
# =========================================================

def register_user(
    user_id: int,
):
    """
    Регистрирует пользователя.

    Для нового пользователя назначается случайное
    время ежедневного уведомления.

    Интервал:
    10:00 — 21:00
    """

    import random
    from datetime import datetime
    from zoneinfo import ZoneInfo

    timezone = ZoneInfo(
        "Europe/Oslo"
    )

    today = (
        datetime
        .now(timezone)
        .date()
        .isoformat()
    )

    connection = get_connection()

    row = connection.execute(
        """
        SELECT
            user_id,
            notification_date,
            notification_minute
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    # -----------------------------------------------------
    # Новый пользователь
    # -----------------------------------------------------

    if row is None:

        notification_minute = random.randint(
            10 * 60,
            21 * 60,
        )

        connection.execute(
            """
            INSERT INTO users (
                user_id,
                notification_date,
                notification_minute
            )
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                today,
                notification_minute,
            ),
        )

    # -----------------------------------------------------
    # Пользователь уже есть,
    # но расписание отсутствует
    # -----------------------------------------------------

    elif (
        row["notification_date"] is None
        or row["notification_minute"] is None
    ):

        notification_minute = random.randint(
            10 * 60,
            21 * 60,
        )

        connection.execute(
            """
            UPDATE users
            SET
                notification_date = ?,
                notification_minute = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                today,
                notification_minute,
                user_id,
            ),
        )

    connection.commit()

    connection.close()


def get_due_notification_users(
    date_iso: str,
    current_minute: int,
):
    """
    Возвращает пользователей,
    которым уже пора отправить
    сегодняшнее уведомление.
    """

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT user_id
        FROM users
        WHERE notification_date < ?
           OR (notification_date = ? AND notification_minute <= ?)
        ORDER BY user_id
        """,
        (
            date_iso,
            date_iso,
            current_minute,
        ),
    ).fetchall()

    connection.close()

    return [
        row["user_id"]
        for row in rows
    ]


def mark_notification_sent(
    user_id: int,
    next_date_iso: str,
    next_minute: int,
):
    """
    После отправки уведомления
    переносим следующее уведомление
    на следующий день.
    """

    connection = get_connection()

    connection.execute(
        """
        UPDATE users
        SET
            notification_date = ?,
            notification_minute = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (
            next_date_iso,
            next_minute,
            user_id,
        ),
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
    stats["feedback"] = get_feedback_stats()
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

    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET ai_result = ?
        WHERE id = ?
        """,
        (
            ai_result,
            story_id,
        ),
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
# SUPPORT
# =========================================================

def detect_dialog_priority(text: str) -> int:
    text = (text or "").lower()
    urgent = (
        "суицид", "самоуб", "убить себя", "не хочу жить",
        "покончу", "порежу себя", "опасно", "угрожают",
        "насилие", "избивают", "угрожает жизни", "кровь",
    )
    high = (
        "паническая атака", "паника", "не могу справиться",
        "срочно", "очень плохо", "кризис", "страшно",
    )
    if any(x in text for x in urgent):
        return 3
    if any(x in text for x in high):
        return 2
    return 1


def log_admin_action(admin_id: int, action: str, entity_type: str, entity_id: int | None = None, details: str | None = None):
    connection = get_connection()
    connection.execute(
        """INSERT INTO audit_logs (admin_id, action, entity_type, entity_id, details)
           VALUES (?, ?, ?, ?, ?)""",
        (admin_id, action, entity_type, entity_id, details),
    )
    connection.commit()
    connection.close()


def get_audit_logs(limit: int = 50):
    connection = get_connection()
    rows = connection.execute(
        """SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    connection.close()
    return rows


def save_support_feedback(dialog_id: int, user_id: int, rating: int, comment: str | None = None):
    rating = max(1, min(5, int(rating)))
    connection = get_connection()
    connection.execute(
        """INSERT INTO support_feedback (dialog_id, user_id, rating, comment)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(dialog_id) DO UPDATE SET rating=excluded.rating, comment=excluded.comment""",
        (dialog_id, user_id, rating, comment),
    )
    connection.commit()
    connection.close()


def get_feedback_stats():
    connection = get_connection()
    row = connection.execute(
        """SELECT COUNT(*) AS count, COALESCE(AVG(rating), 0) AS avg_rating
           FROM support_feedback"""
    ).fetchone()
    connection.close()
    return {"count": row["count"], "avg_rating": round(float(row["avg_rating"] or 0), 2)}


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
            priority,
            unread_admin
        )
        VALUES (
            ?,
            ?,
            'open',
            'new',
            ?,
            1
        )
        """,
        (
            user_id,
            first_message,
            detect_dialog_priority(first_message),
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
                priority = MAX(priority, ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                detect_dialog_priority(text),
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
        ORDER BY d.priority DESC, d.updated_at DESC
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
