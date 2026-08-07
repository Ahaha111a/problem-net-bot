import sqlite3
from datetime import datetime
from config import config

def init_db():
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
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
    try:
        cursor.execute("ALTER TABLE stories ADD COLUMN published_at TIMESTAMP")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE stories ADD COLUMN ai_result TEXT")
    except:
        pass
    conn.commit()
    conn.close()


async def save_story(story_id: int, post_text: str = None):
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
    if post_text:
        cursor.execute("""
            UPDATE stories 
            SET post_text = ?, status = 'published', published_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (post_text, story_id))
    else:
        cursor.execute("UPDATE stories SET status = 'waiting' WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()


async def publish_story(story_id: int):
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE stories SET status = 'published', published_at = CURRENT_TIMESTAMP WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()


async def reject_story(story_id: int):
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE stories SET status = 'rejected' WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()


async def get_story_by_id(story_id: int):
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, text, post_text, status, created_at, published_at 
        FROM stories WHERE id = ?
    """, (story_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "user_id": row[1],
            "text": row[2],
            "post_text": row[3],
            "status": row[4],
            "created_at": row[5],
            "published_at": row[6]
        }
    return None


async def get_all_stories():
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, text, post_text, status, created_at, published_at FROM stories")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "text": r[2], "post_text": r[3],
             "status": r[4], "created_at": r[5], "published_at": r[6]} for r in rows]


async def get_stats():
    conn = sqlite3.connect(config.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stories")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stories WHERE status = 'published'")
    published = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stories WHERE status = 'rejected'")
    rejected = cursor.fetchone()[0]
    conn.close()
    return {
        "total": total,
        "published": published,
        "rejected": rejected,
        "waiting": total - published - rejected
    }
