import sqlite3

def init_db():
    conn = sqlite3.connect("database.db")  # creates/opens database.db in your repo
    c = conn.cursor()

    # Create Premium Requests table
    c.execute("""
    CREATE TABLE IF NOT EXISTS premium_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        status TEXT CHECK(status IN ('pending','granted','rejected')) NOT NULL DEFAULT 'pending'
    )
    """)

    # Example: you can add other tables here too
    # c.execute("""
    # CREATE TABLE IF NOT EXISTS users (
    #     id INTEGER PRIMARY KEY AUTOINCREMENT,
    #     username TEXT NOT NULL,
    #     email TEXT,
    #     password TEXT,
    #     premium INTEGER DEFAULT 0,
    #     ip_address TEXT
    # )
    # """)

    conn.commit()
    conn.close()
    print("Database initialized with premium_requests table.")

if __name__ == "__main__":
    init_db()
