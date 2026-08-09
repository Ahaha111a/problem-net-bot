import sqlite3
from pathlib import Path


DB_PATH = Path("bot.db")


def get_connection():
    connection = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            ai_result TEXT,
            post_text TEXT,
            status TEXT DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dialog_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(dialog_id) REFERENCES support_dialogs(id)
        )
        """
    )

    connection.commit()
    connection.close()


def create_story(user_id: int, text: str):
    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO stories (user_id, text, status)
        VALUES (?, ?, 'waiting')
        """,
        (user_id, text),
    )

    story_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return story_id


def update_ai_result(story_id: int, ai_result: str):
    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET ai_result = ?
        WHERE id = ?
        """,
        (ai_result, story_id),
    )

    connection.commit()
    connection.close()


def update_post(story_id: int, post_text: str):
    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET post_text = ?
        WHERE id = ?
        """,
        (post_text, story_id),
    )

    connection.commit()
    connection.close()


def get_story(story_id: int):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM stories
        WHERE id = ?
        """,
        (story_id,),
    ).fetchone()

    connection.close()

    return row


def publish_story(story_id: int):
    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET status = 'published'
        WHERE id = ?
        """,
        (story_id,),
    )

    connection.commit()
    connection.close()


def reject_story(story_id: int):
    connection = get_connection()

    connection.execute(
        """
        UPDATE stories
        SET status = 'rejected'
        WHERE id = ?
        """,
        (story_id,),
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
        "SELECT COUNT(*) FROM stories"
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


def create_support_dialog(user_id: int, first_message: str):
    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO support_dialogs (
            user_id,
            first_message,
            status,
            support_status,
            unread_admin
        )
        VALUES (?, ?, 'open', 'new', 1)
        """,
        (user_id, first_message),
    )

    dialog_id = cursor.lastrowid

    connection.execute(
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


def get_open_dialog_by_user(user_id: int):
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
        (user_id,),
    ).fetchone()

    connection.close()

    return row


def get_dialog(dialog_id: int):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM support_dialogs
        WHERE id = ?
        """,
        (dialog_id,),
    ).fetchone()

    connection.close()

    return row


def get_dialog_messages(dialog_id: int):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM support_messages
        WHERE dialog_id = ?
        ORDER BY id ASC
        """,
        (dialog_id,),
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
            SET unread_admin = unread_admin + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (dialog_id,),
        )
    else:
        connection.execute(
            """
            UPDATE support_dialogs
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (dialog_id,),
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


def assign_dialog(dialog_id: int, admin_id: int):
    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET assigned_admin_id = ?,
            support_status = 'in_progress',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (admin_id, dialog_id),
    )

    connection.commit()
    connection.close()


def unassign_dialog(dialog_id: int):
    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET assigned_admin_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (dialog_id,),
    )

    connection.commit()
    connection.close()


def close_dialog(dialog_id: int):
    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET status = 'closed',
            support_status = 'closed',
            assigned_admin_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (dialog_id,),
    )

    connection.commit()
    connection.close()


def mark_dialog_read_by_admin(dialog_id: int):
    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET unread_admin = 0
        WHERE id = ?
        """,
        (dialog_id,),
    )

    connection.commit()
    connection.close()


def set_dialog_status(dialog_id: int, status: str):
    connection = get_connection()

    connection.execute(
        """
        UPDATE support_dialogs
        SET support_status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, dialog_id),
    )

    connection.commit()
    connection.close()


def request_personal_contact(dialog_id: int):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT personal_contact_requested
        FROM support_dialogs
        WHERE id = ?
        """,
        (dialog_id,),
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
        SET personal_contact_requested = 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (dialog_id,),
    )

    connection.commit()
    connection.close()

    return True
