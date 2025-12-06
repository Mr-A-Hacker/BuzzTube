import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS premium_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending','granted','rejected')) NOT NULL DEFAULT 'pending'
)
""")

conn.commit()
conn.close()
