import sqlite3


connection = sqlite3.connect("stories.db")

cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


connection.commit()


def save_story(user_id: int, text: str):

    print("💾 История сохранена в базе")

    cursor.execute(
        """
        INSERT INTO stories (user_id, text)
        VALUES (?, ?)
        """,
        (user_id, text)
    )

    connection.commit()

    return cursor.lastrowid


def get_all_stories():

    cursor.execute(
        "SELECT * FROM stories ORDER BY id DESC"
    )

    return cursor.fetchall()
