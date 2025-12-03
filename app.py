import os
import time
from datetime import datetime
from flask import (
    Flask, render_template, redirect, url_for, request,
    session, flash, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# ----------------------------
# App setup
# ----------------------------
app = Flask(__name__)
app.secret_key = "buzz_secret_change_me"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Uploads
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

db = SQLAlchemy(app)

# ----------------------------
# Database models
# ----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # plain text for demo
    premium = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    profile_pic = db.Column(db.String(300), nullable=True)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    uploader = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    likes = db.Column(db.Integer, default=0)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    user = db.Column(db.String(80), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscriber = db.Column(db.String(80), nullable=False)
    creator = db.Column(db.String(80), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80), nullable=False)
    text = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(300), nullable=True)
    gif = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter = db.Column(db.String(80), nullable=False)
    reported_user = db.Column(db.String(80), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Pending")

# ----------------------------
# Helpers
# ----------------------------
def current_user():
    return session.get('user')

def is_admin():
    return bool(session.get('is_admin'))

def require_login():
    if not current_user():
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

def save_upload(file_storage, allowed=('mp4', 'png', 'jpg', 'jpeg', 'gif')):
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename)
    if '.' not in filename:
        return None
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in allowed:
        return None
    path = os.path.join(UPLOAD_DIR, filename)
    base, dotext = filename.rsplit('.', 1)
    counter = 1
    while os.path.exists(path):
        filename = f"{base}_{counter}.{dotext}"
        path = os.path.join(UPLOAD_DIR, filename)
        counter += 1
    file_storage.save(path)
    return filename

# ----------------------------
# Premium enforcement
# ----------------------------
@app.before_request
def enforce_premium_timer():
    endpoint = request.endpoint or ""
    free_endpoints = {'login', 'signup', 'logout', 'static', 'home'}
    if endpoint in free_endpoints:
        return
    if 'user' in session:
        if not session.get('premium', False):
            login_time = session.get('login_time', 0)
            if time.time() - login_time > 600:  # 10 minutes
                session.clear()
                flash("Free access expired. Please upgrade to BuzzTub Premium.", "danger")
                return redirect(url_for('login'))


from datetime import datetime

@app.context_processor
def inject_now():
    return {'datetime': datetime}


# ----------------------------
# Routes: Auth
# ----------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash("Username and password required.", "warning")
            return render_template('signup.html')
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return render_template('signup.html')
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Signup successful. Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user'] = user.username
            session['premium'] = bool(user.premium)
            session['login_time'] = time.time()
            session['is_admin'] = bool(user.is_admin)
            flash(f"Welcome, {user.username}!", "success")
            return redirect(url_for('home'))
        flash("Invalid credentials.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('home'))
# ----------------------------
# Routes: Home + Upload
# ----------------------------
@app.route('/', methods=['GET'])
def home():
    q = request.args.get('q', '').strip()
    if q:
        videos = Video.query.filter(
            (Video.title.ilike(f"%{q}%")) | (Video.uploader.ilike(f"%{q}%"))
        ).order_by(Video.created_at.desc()).all()
    else:
        videos = Video.query.order_by(Video.created_at.desc()).all()
    return render_template('home.html', videos=videos)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if not current_user():
        return require_login()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        file = request.files.get('file')
        if not title or not file:
            flash("Title and video file required.", "warning")
            return render_template('upload.html')
        filename = save_upload(file, allowed=('mp4',))
        if not filename:
            flash("Invalid file type. Only MP4 allowed.", "danger")
            return render_template('upload.html')
        video = Video(title=title, filename=filename, uploader=current_user())
        db.session.add(video)
        db.session.commit()
        flash("Video uploaded successfully!", "success")
        return redirect(url_for('home'))
    return render_template('upload.html')

@app.route('/uploads/<path:filename>')
def uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename)

# ----------------------------
# Routes: Video page + interactions
# ----------------------------
@app.route('/video/<int:id>', methods=['GET'])
def video(id):
    v = Video.query.get_or_404(id)
    comments = Comment.query.filter_by(video_id=v.id).order_by(Comment.created_at.asc()).all()
    return render_template('video.html', video=v, comments=comments)

@app.route('/subscribe/<int:id>', methods=['POST'])
def subscribe(id):
    if not current_user():
        return require_login()
    v = Video.query.get_or_404(id)
    existing = Subscription.query.filter_by(subscriber=current_user(), creator=v.uploader).first()
    if not existing:
        sub = Subscription(subscriber=current_user(), creator=v.uploader, video_id=v.id)
        db.session.add(sub)
        db.session.commit()
        flash(f"Subscribed to {v.uploader}.", "success")
    else:
        flash("Already subscribed.", "info")
    return redirect(url_for('video', id=id))

@app.route('/like/<int:id>', methods=['POST'])
def like(id):
    if not current_user():
        return require_login()
    v = Video.query.get_or_404(id)
    v.likes += 1
    db.session.commit()
    flash("You liked this video.", "success")
    return redirect(url_for('video', id=id))

@app.route('/comment/<int:id>', methods=['POST'])
def comment(id):
    if not current_user():
        return require_login()
    v = Video.query.get_or_404(id)
    text = request.form.get('text', '').strip()
    if text:
        c = Comment(video_id=v.id, user=current_user(), text=text)
        db.session.add(c)
        db.session.commit()
        flash("Comment posted.", "success")
    else:
        flash("Comment cannot be empty.", "warning")
    return redirect(url_for('video', id=id))
# ----------------------------
# Routes: Leaderboard
# ----------------------------
@app.route('/leaderboard')
def leaderboard():
    results = db.session.query(
        Subscription.creator,
        db.func.count(Subscription.id).label('sub_count')
    ).group_by(Subscription.creator).order_by(db.desc('sub_count')).all()
    leaders = [{'username': r[0], 'sub_count': r[1]} for r in results]
    return render_template('leaderboard.html', leaders=leaders)

# ----------------------------
# Routes: Publichat
# ----------------------------
@app.route('/publichat', methods=['GET', 'POST'])
def publichat():
    if request.method == 'POST':
        if not current_user():
            return require_login()
        text = request.form.get('text', '').strip() or None
        image_file = request.files.get('image')
        gif_file = request.files.get('gif')
        image_name = save_upload(image_file, allowed=('png','jpg','jpeg')) if image_file and image_file.filename else None
        gif_name = save_upload(gif_file, allowed=('gif',)) if gif_file and gif_file.filename else None
        msg = ChatMessage(user=current_user(), text=text, image=image_name, gif=gif_name)
        db.session.add(msg)
        db.session.commit()
        flash("Posted to Publichat.", "success")
        return redirect(url_for('publichat'))
    messages = ChatMessage.query.order_by(ChatMessage.created_at.asc()).all()
    return render_template('publichat.html', messages=messages)

# ----------------------------
# Routes: Admin dashboard
# ----------------------------
@app.route('/admin')
def admin():
    if not current_user() or not is_admin():
        flash("Admin access required.", "danger")
        return redirect(url_for('home'))
    videos = Video.query.all()
    comments = (
        db.session.query(Comment, Video.title.label('video_title'))
        .join(Video, Video.id == Comment.video_id).all()
    )
    comments_flat = [
        type('CView', (), {
            'id': c.Comment.id,
            'user': c.Comment.user,
            'text': c.Comment.text,
            'video_title': c.video_title
        }) for c in comments
    ]
    users = User.query.all()
    reports = Report.query.all()
    return render_template('admin.html', videos=videos, comments=comments_flat, users=users, reports=reports)
# ----------------------------
# Admin actions
# ----------------------------
@app.route('/delete_video/<int:id>', methods=['POST'])
def delete_video(id):
    if not is_admin():
        return redirect(url_for('home'))
    v = Video.query.get_or_404(id)
    Comment.query.filter_by(video_id=v.id).delete()
    Subscription.query.filter_by(video_id=v.id).delete()
    db.session.delete(v)
    db.session.commit()
    flash("Video deleted.", "info")
    return redirect(url_for('admin'))

@app.route('/delete_comment/<int:id>', methods=['POST'])
def delete_comment(id):
    if not is_admin():
        return redirect(url_for('home'))
    c = Comment.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Comment deleted.", "info")
    return redirect(url_for('admin'))

@app.route('/grant_premium/<int:id>', methods=['POST'])
def grant_premium(id):
    if not is_admin():
        return redirect(url_for('home'))
    u = User.query.get_or_404(id)
    u.premium = True
    db.session.commit()
    flash(f"Granted premium to {u.username}.", "success")
    return redirect(url_for('admin'))

@app.route('/kick_user/<int:id>', methods=['POST'])
def kick_user(id):
    if not is_admin():
        return redirect(url_for('home'))
    u = User.query.get_or_404(id)
    if u.username == current_user():
        session.clear()
    flash(f"Kicked {u.username}.", "warning")
    return redirect(url_for('admin'))

# ----------------------------
# Routes: Settings (profile pic, password)
# ----------------------------
@app.route('/settings')
def settings():
    if not current_user():
        return require_login()
    u = User.query.filter_by(username=current_user()).first()
    return render_template('settings.html', user=u)

@app.route('/update_pic', methods=['POST'])
def update_pic():
    if not current_user():
        return require_login()
    file = request.files.get('pic')
    filename = save_upload(file, allowed=('png','jpg','jpeg'))
    if filename:
        u = User.query.filter_by(username=current_user()).first()
        u.profile_pic = filename
        db.session.commit()
        flash("Profile picture updated!", "success")
    return redirect(url_for('settings'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if not current_user():
        return require_login()
    old = request.form.get('old')
    new = request.form.get('new')
    u = User.query.filter_by(username=current_user(), password=old).first()
    if u:
        u.password = new
        db.session.commit()
        flash("Password changed successfully!", "success")
    else:
        flash("Old password incorrect.", "danger")
    return redirect(url_for('settings'))

# ----------------------------
# Routes: Reports
# ----------------------------
@app.route('/report/<username>', methods=['POST'])
def report_user(username):
    if not current_user():
        return require_login()
    reason = request.form.get('reason', '').strip()
    if reason:
        report = Report(reporter=current_user(), reported_user=username, reason=reason)
        db.session.add(report)
        db.session.commit()
        flash("User reported. Admin will review.", "info")
    return redirect(url_for('home'))

@app.route('/mark_report_reviewed/<int:id>', methods=['POST'])
def mark_report_reviewed(id):
    if not is_admin():
        return redirect(url_for('home'))
    r = Report.query.get_or_404(id)
    r.status = "Reviewed"
    db.session.commit()
    flash("Report marked as reviewed.", "info")
    return redirect(url_for('admin'))

# ----------------------------
# Routes: Profile (self + public)
# ----------------------------
@app.route('/profile')
def profile():
    if not current_user():
        return require_login()
    u = User.query.filter_by(username=current_user()).first()
    videos = Video.query.filter_by(uploader=current_user()).all()
    subs = Subscription.query.filter_by(subscriber=current_user()).all()
    return render_template('profile.html', user=u, videos=videos, subs=subs)

@app.route('/user/<username>')
def user_profile(username):
    u = User.query.filter_by(username=username).first_or_404()
    videos = Video.query.filter_by(uploader=username).all()
    return render_template('user_profile.html', user=u, videos=videos)

@app.route('/subscribe_user/<username>', methods=['POST'])
def subscribe_user(username):
    if not current_user():
        return require_login()
    existing = Subscription.query.filter_by(subscriber=current_user(), creator=username).first()
    if not existing:
        sub = Subscription(subscriber=current_user(), creator=username)
        db.session.add(sub)
        db.session.commit()
        flash(f"Subscribed to {username}.", "success")
    else:
        flash("Already subscribed.", "info")
    return redirect(url_for('user_profile', username=username))

# ----------------------------
# App run
# ----------------------------
db_initialized = False

@app.before_request
def init_db_once():
    global db_initialized
    if not db_initialized:
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                password='admin',   # ⚠️ Plain text for demo; use hashing in production
                premium=True,
                is_admin=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created: username='admin', password='admin'")
        db_initialized = True

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
