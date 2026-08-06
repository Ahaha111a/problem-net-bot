import sqlite3


connection = sqlite3.connect("stories.db", check_same_thread=False)

cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    post_text TEXT,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


connection.commit()


# Проверяем, есть ли новые столбцы
cursor.execute("PRAGMA table_info(stories)")
columns = [column[1] for column in cursor.fetchall()]

if "post_text" not in columns:
    cursor.execute("ALTER TABLE stories ADD COLUMN post_text TEXT")

if "status" not in columns:
    cursor.execute("ALTER TABLE stories ADD COLUMN status TEXT DEFAULT 'draft'")

connection.commit()


def save_story(user_id: int, text: str):

    cursor.execute(
        """
        INSERT INTO stories (user_id, text)
        VALUES (?, ?)
        """,
        (user_id, text)
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
        (post_text, story_id)
    )

    connection.commit()


def get_post(story_id: int):

    cursor.execute(
        """
        SELECT post_text
        FROM stories
        WHERE id = ?
        """,
        (story_id,)
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    return None


def publish_story(story_id: int):

    cursor.execute(
        """
        UPDATE stories
        SET status='published'
        WHERE id=?
        """,
        (story_id,)
    )

    connection.commit()


def get_all_stories():

    cursor.execute(
        "SELECT * FROM stories ORDER BY id DESC"
    )

    return cursor.fetchall()
