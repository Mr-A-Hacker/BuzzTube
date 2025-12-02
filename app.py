from flask import Flask, render_template, redirect, url_for, request, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "buzz_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    premium = db.Column(db.Boolean, default=False)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        user = User(username=request.form['username'], password=request.form['password'])
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username'], password=request.form['password']).first()
        if user:
            session['user'] = user.username
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

if __name__ == "__main__":
    db.create_all()
    app.run(debug=True)
