import sqlite3
from datetime import datetime

from config import DB_PATH


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_connection()

    cursor = connection.cursor()

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

    connection.commit()
    connection.close()


def create_story(user_id: int, text: str):
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
        (user_id, text)
    )

    story_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return story_id


def get_story(story_id: int):
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM stories
        WHERE id = ?
        """,
        (story_id,)
    )

    story = cursor.fetchone()

    connection.close()

    return story


def update_ai_result(story_id: int, ai_result: str):
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE stories
        SET ai_result = ?
        WHERE id = ?
        """,
        (ai_result, story_id)
    )

    connection.commit()
    connection.close()


def update_post(story_id: int, post_text: str):
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE stories
        SET post_text = ?
        WHERE id = ?
        """,
        (post_text, story_id)
    )

    connection.commit()
    connection.close()


def get_waiting_stories():
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM stories
        WHERE status = 'waiting'
        ORDER BY id DESC
        """
    )

    stories = cursor.fetchall()

    connection.close()

    return stories


def publish_story(story_id: int):
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE stories
        SET status = 'published',
            published_at = ?
        WHERE id = ?
        """,
        (datetime.now(), story_id)
    )

    connection.commit()
    connection.close()


def reject_story(story_id: int):
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE stories
        SET status = 'rejected'
        WHERE id = ?
        """,
        (story_id,)
    )

    connection.commit()
    connection.close()


def get_all_stories():
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM stories
        ORDER BY id DESC
        """
    )

    stories = cursor.fetchall()

    connection.close()

    return stories


def get_stats():
    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
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
    )

    stats = cursor.fetchone()

    connection.close()

    return {
        "total": stats["total"] or 0,
        "waiting": stats["waiting"] or 0,
        "published": stats["published"] or 0,
        "rejected": stats["rejected"] or 0,
    }
