from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import sqlite3, os, time
from functools import wraps

# --- Flask app setup ---
app = Flask(__name__)
app.secret_key = "supersecretkey"   # ⚠️ replace with env var in production
DB_FILE = "buzz.db"

# --- Uploads folder setup ---
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# --- Database helper ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            premium INTEGER DEFAULT 0,
            ip_address TEXT
        )
    """)

    # Videos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            uploader TEXT NOT NULL,
            filepath TEXT,
            likes INTEGER DEFAULT 0
        )
    """)

    # Likes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            user TEXT,
            UNIQUE(video_id, user)
        )
    """)

    # Comments
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            user TEXT,
            text TEXT
        )
    """)

    # Messages (Public Chat)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            message TEXT
        )
    """)

    # Reports
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter TEXT,
            reported_user TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)

    # Follows
    cur.execute("""
        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower TEXT,
            following TEXT
        )
    """)

    # Blocked IPs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blocked_ips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT UNIQUE
        )
    """)

    # Premium Requests
    cur.execute("""
        CREATE TABLE IF NOT EXISTS premium_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            status TEXT CHECK(status IN ('pending','granted','rejected')) NOT NULL DEFAULT 'pending'
        )
    """)

# Messages (Public Chat)
cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        message TEXT,
        recipient TEXT
    )
""")

    conn.commit()
    conn.close()

# Initialize DB at startup
init_db()

# Middleware: block requests if IP is in blocked list
@app.before_request
def check_ip_block():
    ip = request.remote_addr
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM blocked_ips WHERE ip_address=?", (ip,))
    if cur.fetchone():
        conn.close()
        abort(403)  # Forbidden
    conn.close()

# Premium decorator
def premium_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("You must log in first.", "warning")
            return redirect(url_for("login"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT premium FROM users WHERE username=?", (session["user"],))
        user = cur.fetchone()
        conn.close()

        if not user:
            session.clear()
            flash("Your account no longer exists. Please sign up again.", "danger")
            return redirect(url_for("signup"))

        if int(user["premium"]) != 1:
            flash("Premium access required.", "danger")
            return redirect(url_for("upgrade"))

        return f(*args, **kwargs)
    return decorated_function
