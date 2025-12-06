import sqlite3

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Premium Requests table
    c.execute("""
    CREATE TABLE IF NOT EXISTS premium_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        status TEXT CHECK(status IN ('pending','granted','rejected')) NOT NULL DEFAULT 'pending'
    )
    """)

    conn.commit()
    conn.close()
    print("✅ premium_requests table ensured.")
