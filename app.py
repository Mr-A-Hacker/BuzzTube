from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, time
from functools import wraps
import werkzeug

app = Flask(__name__)
app.secret_key = "supersecretkey"   # replace with env var in production
DB_FILE = "buzz.db"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Users table with email included
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            premium INTEGER DEFAULT 0
        )
    """)

    # Try to add email column if missing (for old deployments)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT UNIQUE;")
    except sqlite3.OperationalError:
        # Column already exists, ignore
        pass

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

    # Follows
    cur.execute("""
        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower TEXT,
            following TEXT
        )
    """)

    conn.commit()
    conn.close()

# Initialize DB at startup
init_db()

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

        if user["premium"] == 0:
            start = session.get("login_time", 0)
            now = int(time.time())
            if now - start > 600:  # 10 minutes
                session.clear()
                flash("Your free 10‑minute session expired. Upgrade to premium!", "danger")
                return redirect(url_for("login"))

        return f(*args, **kwargs)
    return decorated_function


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")

        # Server-side validation
        if not email or not username or not password:
            flash("Email, username, and password are required.", "danger")
            return redirect(url_for("signup"))

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (email, username, password, premium) VALUES (?, ?, ?, ?)",
                (email, username, password, 0)
            )
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email or username already exists.", "danger")
        finally:
            conn.close()
    return render_template("signup.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")

        # Server-side validation
        if not email or not username or not password:
            flash("Email, username, and password are required.", "danger")
            return redirect(url_for("login"))

        conn = get_db()
        cur = conn.cursor()
        # Match all three fields
        cur.execute(
            "SELECT * FROM users WHERE email=? AND username=? AND password=?",
            (email, username, password)
        )
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

    premium = 0
    cur.execute("SELECT premium FROM users WHERE username=?", (session["user"],))
    user = cur.fetchone()
    if user:
        premium = user["premium"]

    conn.close()
    return render_template("home.html", videos=videos, premium=premium)

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

    cur.execute("SELECT premium FROM users WHERE username=?", (session["user"],))
    user = cur.fetchone()
    conn.close()

    premium = user["premium"] if user else 0
    return render_template("video.html", v=v, comments=comments, premium=premium)


@app.route("/upload", methods=["GET", "POST"])
@premium_required
def upload():
    if request.method == "POST":
        # Safely get title
        title = request.form.get("title")
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("upload"))

        # Safely get file
        file = request.files.get("file")
        if not file or file.filename.strip() == "":
            flash("No file selected.", "danger")
            return redirect(url_for("upload"))

        try:
            # Secure filename
            filename = werkzeug.utils.secure_filename(file.filename)

            # Ensure upload folder exists
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

            # Save file
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            # Web path for serving
            web_path = url_for("static", filename=f"uploads/{filename}")

            # Insert into DB
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO videos (title, uploader, filepath) VALUES (?, ?, ?)",
                (title, session["user"], web_path)
            )
            conn.commit()
            conn.close()

            flash("Video uploaded successfully!", "success")
            return redirect(url_for("home"))

        except Exception as e:
            # Catch unexpected errors so Railway doesn't crash
            flash(f"Upload failed: {e}", "danger")
            return redirect(url_for("upload"))

    return render_template("upload.html")



@app.route("/leaderboard")
@premium_required
def leaderboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT title, likes FROM videos ORDER BY likes DESC LIMIT 5")
    videos = cur.fetchall()
    conn.close()

    titles = [v["title"] for v in videos]
    likes = [v["likes"] for v in videos]

    return render_template("leaderboard.html", titles=titles, likes=likes, videos=videos)


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
    cur.execute("SELECT following FROM follows WHERE follower=?", (session["user"],))
    subs = cur.fetchall()
    conn.close()

    return render_template("profile.html", user=user, videos=videos, subs=subs)


@app.route("/settings", methods=["GET", "POST"])
@premium_required
def settings():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        new_username = request.form.get("username")
        new_password = request.form.get("password")

        # Update username
        if new_username:
            cur.execute("UPDATE users SET username=? WHERE username=?", 
                        (new_username, session["user"]))
            session["user"] = new_username  # update session

        # Update password
        if new_password:
            cur.execute("UPDATE users SET password=? WHERE username=?", 
                        (new_password, session["user"]))

        conn.commit()
        flash("Settings updated!", "success")

    # Fetch user info
    cur.execute("SELECT * FROM users WHERE username=?", (session["user"],))
    user = cur.fetchone()
    conn.close()

    return render_template("settings.html", user=user)

@app.route("/like/<int:id>", methods=["POST"])
@premium_required
def like_video(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE id=?", (id,))
    video = cur.fetchone()
    if not video:
        conn.close()
        flash("Video not found.", "danger")
        return redirect(url_for("home"))

    # Prevent self-like
    if video["uploader"] == session["user"]:
        conn.close()
        flash("You cannot like your own video.", "warning")
        return redirect(url_for("video", id=id))

    # Check if user already liked
    cur.execute("SELECT * FROM likes WHERE video_id=? AND user=?", (id, session["user"]))
    existing = cur.fetchone()

    if existing:
        # Unlike
        cur.execute("DELETE FROM likes WHERE video_id=? AND user=?", (id, session["user"]))
        cur.execute("UPDATE videos SET likes = likes - 1 WHERE id=?", (id,))
        flash("You unliked the video.", "info")
    else:
        # Like
        cur.execute("INSERT INTO likes (video_id, user) VALUES (?, ?)", (id, session["user"]))
        cur.execute("UPDATE videos SET likes = likes + 1 WHERE id=?", (id,))
        flash("You liked the video!", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("video", id=id))


@app.route("/follow/<string:username>", methods=["POST"])
@premium_required
def follow_user(username):
    conn = get_db()
    cur = conn.cursor()

    if username == session["user"]:
        conn.close()
        flash("You cannot follow yourself.", "warning")
        return redirect(url_for("profile"))

    cur.execute("SELECT * FROM follows WHERE follower=? AND following=?", (session["user"], username))
    existing = cur.fetchone()

    if existing:
        flash(f"You already follow {username}.", "info")
    else:
        cur.execute("INSERT INTO follows (follower, following) VALUES (?, ?)", (session["user"], username))
        conn.commit()
        flash(f"You are now following {username}!", "success")

    conn.close()
    return redirect(url_for("profile"))


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
    cur.execute("SELECT * FROM messages")
    messages = cur.fetchall()
    conn.close()

    return render_template("admin.html",
                           videos=videos,
                           comments=comments,
                           users=users,
                           reports=reports,
                           messages=messages)


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


@app.route("/admin/delete_message/<int:id>", methods=["POST"])
def admin_delete_message(id):
    if not session.get("admin"):
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Message deleted.", "info")
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
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
