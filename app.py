from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, time
from functools import wraps

app = Flask(__name__)
app.secret_key = "supersecretkey"   # replace with env var in production
DB_FILE = "buzz.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            premium INTEGER DEFAULT 0
        )
    """)

    # Videos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            uploader TEXT NOT NULL,
            likes INTEGER DEFAULT 0
        )
    """)

    # Comments
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            user TEXT,
            text TEXT,
            FOREIGN KEY(video_id) REFERENCES videos(id)
        )
    """)

    # Messages (Publichat)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            message TEXT
        )
    """)

    # Reports (Admin)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter TEXT,
            reported_user TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)

    conn.commit()
    conn.close()

# Initialize DB at startup
init_db()
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

        # Non-premium timeout check
        if user and user["premium"] == 0:
            start = session.get("login_time", 0)
            now = int(time.time())
            if now - start > 600:  # 600 seconds = 10 minutes
                session.clear()
                flash("Your free 10‑minute session expired. Upgrade to premium!", "danger")
                return redirect(url_for("login"))

        return f(*args, **kwargs)
    return decorated_function
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password, premium) VALUES (?, ?, ?)",
                        (username, password, 0))
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
        finally:
            conn.close()
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["admin"] = (user["username"] == "admin")
            session["login_time"] = int(time.time())
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))
@app.route("/")
@premium_required
def home():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos ORDER BY id DESC")
    videos = cur.fetchall()
    conn.close()
    return render_template("home.html", videos=videos)


@app.route("/video/<int:id>", methods=["GET", "POST"])
@premium_required
def video(id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        text = request.form["text"]
        cur.execute("INSERT INTO comments (video_id, user, text) VALUES (?, ?, ?)",
                    (id, session["user"], text))
        conn.commit()

    cur.execute("SELECT * FROM videos WHERE id=?", (id,))
    v = cur.fetchone()
    cur.execute("SELECT * FROM comments WHERE video_id=?", (id,))
    comments = cur.fetchall()
    conn.close()

    return render_template("video.html", v=v, comments=comments)


@app.route("/upload", methods=["GET", "POST"])
@premium_required
def upload():
    if request.method == "POST":
        title = request.form["title"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO videos (title, uploader) VALUES (?, ?)",
                    (title, session["user"]))
        conn.commit()
        conn.close()
        flash("Video uploaded successfully!", "success")
        return redirect(url_for("home"))
    return render_template("upload.html")


@app.route("/leaderboard")
@premium_required
def leaderboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos ORDER BY likes DESC LIMIT 10")
    videos = cur.fetchall()
    conn.close()
    return render_template("leaderboard.html", videos=videos)


@app.route("/publichat", methods=["GET", "POST"])
@premium_required
def publichat():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        msg = request.form["message"]
        cur.execute("INSERT INTO messages (user, message) VALUES (?, ?)",
                    (session["user"], msg))
        conn.commit()

    cur.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 20")
    messages = cur.fetchall()
    conn.close()

    return render_template("publichat.html", messages=messages)


@app.route("/profile")
@premium_required
def profile():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE uploader=?", (session["user"],))
    videos = cur.fetchall()
    cur.execute("SELECT * FROM users WHERE username=?", (session["user"],))
    user = cur.fetchone()
    conn.close()

    subs = []  # placeholder for subscriptions
    return render_template("profile.html", user=user, videos=videos, subs=subs)


@app.route("/settings", methods=["GET", "POST"])
@premium_required
def settings():
    if request.method == "POST":
        flash("Settings updated!", "success")
        return redirect(url_for("profile"))
    return render_template("settings.html")
@app.route("/admin")
def admin_dashboard():
    if not session.get("admin"):
        flash("Admin access required.", "danger")
        return redirect(url_for("home"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos")
    videos = cur.fetchall()
    cur.execute("SELECT * FROM comments")
    comments = cur.fetchall()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.execute("SELECT * FROM reports")
    reports = cur.fetchall()
    conn.close()

    return render_template("admin.html", videos=videos, comments=comments, users=users, reports=reports)


@app.route("/admin/delete_video/<int:id>", methods=["POST"])
def admin_delete_video(id):
    if not session.get("admin"):
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM videos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Video deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete_comment/<int:id>", methods=["POST"])
def admin_delete_comment(id):
    if not session.get("admin"):
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM comments WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Comment deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/grant_premium/<int:id>", methods=["POST"])
def admin_grant_premium(id):
    if not session.get("admin"):
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET premium=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Premium granted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/kick_user/<int:id>", methods=["POST"])
def admin_kick_user(id):
    if not session.get("admin"):
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("User kicked.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/mark_report_reviewed/<int:id>", methods=["POST"])
def admin_mark_report_reviewed(id):
    if not session.get("admin"):
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE reports SET status='reviewed' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Report marked as reviewed.", "success")
    return redirect(url_for("admin_dashboard"))
if __name__ == "__main__":
    # Ensure DB schema exists before serving
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
