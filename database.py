import sqlite3


connection = sqlite3.connect(
    "stories.db",
    check_same_thread=False
)

cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    post_text TEXT,
    status TEXT DEFAULT 'waiting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


connection.commit()


def save_story(user_id: int, text: str):

    cursor.execute(
        """
        INSERT INTO stories (
            user_id,
            text
        )
        VALUES (?, ?)
        """,
        (
            user_id,
            text
        )
    )

    connection.commit()

    return cursor.lastrowid



def save_post(story_id: int, post_text: str):

    cursor.execute(
        """
        UPDATE stories
        SET post_text = ?
        WHERE id = ?
        """,
        (
            post_text,
            story_id
        )
    )

    connection.commit()



def get_post(story_id: int):

    cursor.execute(
        """
        SELECT post_text
        FROM stories
        WHERE id = ?
        """,
        (
            story_id,
        )
    )

    result = cursor.fetchone()

    if result:
        return result[0]

    return None



def publish_story(story_id: int):

    cursor.execute(
        """
        UPDATE stories
        SET status = 'published'
        WHERE id = ?
        """,
        (
            story_id,
        )
    )

    connection.commit()



def reject_story(story_id: int):

    cursor.execute(
        """
        UPDATE stories
        SET status = 'rejected'
        WHERE id = ?
        """,
        (
            story_id,
        )
    )

    connection.commit()



def get_waiting_stories():

    cursor.execute(
        """
        SELECT id, text, created_at
        FROM stories
        WHERE status = 'waiting'
        ORDER BY id DESC
        """
    )

    return cursor.fetchall()



def get_all_stories():

    cursor.execute(
        """
        SELECT *
        FROM stories
        ORDER BY id DESC
        """
    )

    return cursor.fetchall()



def get_stats():

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM stories
        """
    )

    total = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM stories
        WHERE status = 'published'
        """
    )

    published = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM stories
        WHERE status = 'rejected'
        """
    )

    rejected = cursor.fetchone()[0]


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM stories
        WHERE status = 'waiting'
        """
    )

    waiting = cursor.fetchone()[0]


    return {
        "total": total,
        "published": published,
        "rejected": rejected,
        "waiting": waiting
    }
