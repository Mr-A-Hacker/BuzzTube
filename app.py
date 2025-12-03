from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_PATH = "buzz.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            flash("You must log in or sign up to access this page.", "warning")
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
        cur.execute("INSERT INTO users (username, password, premium) VALUES (?, ?, ?)",
                    (username, password, 0))
        conn.commit()
        conn.close()
        flash("Signup successful! Please log in.", "success")
        return redirect(url_for("login"))
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
            flash(f"Welcome, {user['username']}!", "success")
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
@login_required
def home():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos")
    videos = cur.fetchall()
    conn.close()
    return render_template("home.html", videos=videos)

@app.route("/video/<int:id>")
@login_required
def video_page(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE id=?", (id,))
    v = cur.fetchone()
    cur.execute("SELECT * FROM comments WHERE video_id=?", (id,))
    comments = cur.fetchall()
    conn.close()
    return render_template("video.html", v=v, comments=comments)

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_video():
    if request.method == "POST":
        title = request.form["title"]
        uploader = session["user"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO videos (title, uploader, likes) VALUES (?, ?, ?)",
                    (title, uploader, 0))
        conn.commit()
        conn.close()
        flash("Video uploaded!", "success")
        return redirect(url_for("home"))
    return render_template("upload.html")

@app.route("/leaderboard")
@login_required
def leaderboard_page():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos ORDER BY likes DESC LIMIT 10")
    videos = cur.fetchall()
    conn.close()
    return render_template("leaderboard.html", videos=videos)

@app.route("/publichat", methods=["GET", "POST"])
@login_required
def publichat_page():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        msg = request.form["message"]
        cur.execute("INSERT INTO chat (user, message) VALUES (?, ?)", (session["user"], msg))
        conn.commit()
    cur.execute("SELECT * FROM chat ORDER BY id DESC LIMIT 20")
    messages = cur.fetchall()
    conn.close()
    return render_template("publichat.html", messages=messages)

@app.route("/profile")
@login_required
def profile_page():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE uploader=?", (session["user"],))
    videos = cur.fetchall()
    cur.execute("SELECT * FROM subscriptions WHERE user=?", (session["user"],))
    subs = cur.fetchall()
    conn.close()
    return render_template("profile.html", user={"username":session["user"]}, videos=videos, subs=subs)

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    if request.method == "POST":
        flash("Settings updated!", "info")
    return render_template("settings.html", user={"username":session["user"]})
@app.route("/admin")
@login_required
def admin_dashboard():
    if not session.get("admin"):
        flash("Access denied.", "danger")
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

@app.route("/delete_video/<int:id>", methods=["POST"])
@login_required
def admin_delete_video(id):
    if not session.get("admin"):
        flash("Access denied.", "danger")
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM videos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Video deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/delete_comment/<int:id>", methods=["POST"])
@login_required
def admin_delete_comment(id):
    if not session.get("admin"):
        flash("Access denied.", "danger")
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM comments WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Comment deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/grant_premium/<int:id>", methods=["POST"])
@login_required
def admin_grant_premium(id):
    if not session.get("admin"):
        flash("Access denied.", "danger")
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET premium=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("User granted premium status.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/kick_user/<int:id>", methods=["POST"])
@login_required
def admin_kick_user(id):
    if not session.get("admin"):
        flash("Access denied.", "danger")
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("User removed.", "warning")
    return redirect(url_for("admin_dashboard"))

@app.route("/mark_report_reviewed/<int:id>", methods=["POST"])
@login_required
def admin_mark_report_reviewed(id):
    if not session.get("admin"):
        flash("Access denied.", "danger")
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE reports SET status='Reviewed' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Report marked as reviewed.", "info")
    return redirect(url_for("admin_dashboard"))

# Initialize schema if missing
if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        conn = get_db()
        cur = conn.cursor()
        # Schema creation
        cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, premium INTEGER)")
        cur.execute("CREATE TABLE videos (id INTEGER PRIMARY KEY, title TEXT, uploader TEXT, likes INTEGER)")
        cur.execute("CREATE TABLE comments (id INTEGER PRIMARY KEY, video_id INTEGER, user TEXT, text TEXT)")
        cur.execute("CREATE TABLE chat (id INTEGER PRIMARY KEY, user TEXT, message TEXT)")
        cur.execute("CREATE TABLE subscriptions (id INTEGER PRIMARY KEY, user TEXT, creator TEXT)")
        cur.execute("CREATE TABLE reports (id INTEGER PRIMARY KEY, reporter TEXT, reported_user TEXT, reason TEXT, status TEXT)")
        # Insert starter admin account
        cur.execute("INSERT INTO users (username, password, premium) VALUES (?, ?, ?)", ("admin", "admin", 1))
        conn.commit()
        conn.close()

    # Run the app
    app.run(debug=True)
