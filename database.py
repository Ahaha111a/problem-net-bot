import sqlite3
from datetime import datetime

from config import DB_PATH


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# =========================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# =========================================================

def init_db():

    connection = get_connection()
    cursor = connection.cursor()

    # =====================================================
    # ИСТОРИИ
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            ai_result TEXT,
            post_text TEXT,
            status TEXT NOT NULL DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TIMESTAMP
        )
    """)

    # =====================================================
    # ДИАЛОГИ ПОДДЕРЖКИ
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_dialogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            assigned_admin_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message TEXT,
            unread_admin INTEGER NOT NULL DEFAULT 0,
            unread_user INTEGER NOT NULL DEFAULT 0
        )
    """)

    # =====================================================
    # МИГРАЦИЯ СТАРОЙ БАЗЫ
    # =====================================================

    try:

        cursor.execute(
            """
            ALTER TABLE support_dialogs
            ADD COLUMN unread_admin
            INTEGER NOT NULL DEFAULT 0
            """
        )

    except sqlite3.OperationalError:
        pass

    try:

        cursor.execute(
            """
            ALTER TABLE support_dialogs
            ADD COLUMN unread_user
            INTEGER NOT NULL DEFAULT 0
            """
        )

    except sqlite3.OperationalError:
        pass

    # =====================================================
    # СООБЩЕНИЯ ДИАЛОГОВ
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dialog_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


# =========================================================
# ИСТОРИИ
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


def get_story(
    story_id: int,
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM stories
        WHERE id = ?
        """,
        (
            story_id,
        ),
    )

    story = cursor.fetchone()

    connection.close()

    return story


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


def get_waiting_stories():

    connection = get_connection()

    stories = connection.execute(
        """
        SELECT *
        FROM stories
        WHERE status = 'waiting'
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return stories


def publish_story(
    story_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET status = 'published',
            published_at = ?
        WHERE id = ?
        """,
        (
            datetime.now(),
            story_id,
        ),
    )

    connection.commit()
    connection.close()


def reject_story(
    story_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET status = 'rejected'
        WHERE id = ?
        """,
        (
            story_id,
        ),
    )

    connection.commit()
    connection.close()


def get_all_stories():

    connection = get_connection()

    stories = connection.execute(
        """
        SELECT *
        FROM stories
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return stories


def get_stats():

    connection = get_connection()

    stats = connection.execute(
        """
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'waiting'
                    THEN 1
                    ELSE 0
                END
            ) AS waiting,

            SUM(
                CASE
                    WHEN status = 'published'
                    THEN 1
                    ELSE 0
                END
            ) AS published,

            SUM(
                CASE
                    WHEN status = 'rejected'
                    THEN 1
                    ELSE 0
                END
            ) AS rejected

        FROM stories
        """
    ).fetchone()

    connection.close()

    return {
        "total": stats["total"] or 0,
        "waiting": stats["waiting"] or 0,
        "published": stats["published"] or 0,
        "rejected": stats["rejected"] or 0,
    }


# =========================================================
# ДИАЛОГИ ПОДДЕРЖКИ
# =========================================================

def get_open_dialog_by_user(
    user_id: int,
):

    connection = get_connection()

    dialog = connection.execute(
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

    return dialog


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
            status,
            last_message,
            unread_admin,
            unread_user
        )
        VALUES (?, 'open', ?, 1, 0)
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


def add_support_message(
    dialog_id: int,
    sender_id: int,
    sender_type: str,
    text: str,
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
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

        cursor.execute(
            """
            UPDATE support_dialogs
            SET
                last_message = ?,
                updated_at = CURRENT_TIMESTAMP,
                unread_admin = unread_admin + 1
            WHERE id = ?
            """,
            (
                text,
                dialog_id,
            ),
        )

    else:

        cursor.execute(
            """
            UPDATE support_dialogs
            SET
                last_message = ?,
                updated_at = CURRENT_TIMESTAMP,
                unread_user = unread_user + 1
            WHERE id = ?
            """,
            (
                text,
                dialog_id,
            ),
        )

    connection.commit()
    connection.close()


def get_dialog(
    dialog_id: int,
):

    connection = get_connection()

    dialog = connection.execute(
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

    return dialog


def get_open_dialogs():

    connection = get_connection()

    dialogs = connection.execute(
        """
        SELECT *
        FROM support_dialogs
        WHERE status = 'open'
        ORDER BY updated_at DESC, id DESC
        """
    ).fetchall()

    connection.close()

    return dialogs


def get_dialog_messages(
    dialog_id: int,
):

    connection = get_connection()

    messages = connection.execute(
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

    return messages


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


def close_dialog(
    dialog_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET
            status = 'closed',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    )

    connection.commit()
    connection.close()


# =========================================================
# ПРОЧИТАНО
# =========================================================

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


def mark_dialog_read_by_user(
    dialog_id: int,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET unread_user = 0
        WHERE id = ?
        """,
        (
            dialog_id,
        ),
    )

    connection.commit()
    connection.close()
