import sqlite3
import os

DB_PATH = "sharedvideo/statistics.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, videos_played INTEGER)"
    )
    conn.execute("INSERT OR IGNORE INTO stats (id, videos_played) VALUES (1, 0)")
    return conn

def increment_video_stat():
    conn = get_connection()
    conn.execute("UPDATE stats SET videos_played = videos_played + 1 WHERE id = 1")
    conn.commit()
    conn.close()

def get_video_stat():
    conn = get_connection()
    cur = conn.execute("SELECT videos_played FROM stats WHERE id = 1")
    result = cur.fetchone()[0]
    conn.close()
    return result