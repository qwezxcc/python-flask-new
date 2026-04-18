import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime


app = Flask(__name__) 
app.config['SECRET_KEY'] = 'super-secret-gamer-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gamerportal.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Обмеження 16MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Будь ласка, увійдіть, щоб отримати доступ до цієї сторінки."
login_manager.login_message_category = "warning"


# МОДЕЛІ БАЗИ ДАНИХ (MODELS) =======================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Integer, nullable=False, default=0)    
    
    games = db.relationship('Game', backref='owner', lazy=True)
    news = db.relationship('News', backref='author', lazy=True)

class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=True) 
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    file_name = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

class News(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# МАРШРУТИ (ROUTES) ==========================================

@app.route('/')
def index():
    recent_news = News.query.order_by(News.date_posted.desc()).limit(3).all()
    # Також додаємо вивід ігор на головну, якщо потрібно
    recent_games = Game.query.order_by(Game.date_added.desc()).limit(6).all()
    print('-----',recent_games)
    return render_template('index.html', news_list=recent_news, games=recent_games)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()
        if user_exists or email_exists:
            flash('Користувач з таким нікнеймом або email вже існує!', 'error')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Реєстрація успішна! Тепер ви можете увійти.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f'З поверненням, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Невірний логін або пароль. Спробуйте ще раз.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Ви успішно вийшли з системи.', 'success')
    return redirect(url_for('index'))

@app.route('/news')
@login_required 
def news():
    all_news = News.query.order_by(News.date_posted.desc()).limit(10).all()
    return render_template('news.html', news_list=all_news)

@app.route('/news/<int:news_id>')
@login_required
def view_news(news_id):
    post = News.query.get_or_404(news_id)
    return render_template('news_detail.html', post=post)

@app.route('/addnews', methods=['GET', 'POST'])
@login_required
def addnews():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        new_post = News(title=title, content=content, author=current_user)
        db.session.add(new_post)
        db.session.commit()
        flash('Новину успішно опубліковано!', 'success')
        return redirect(url_for('news'))
    return render_template('addnews.html')

@app.route('/my_library', methods=['GET', 'POST'])
@login_required
def my_library():
    if request.method == 'POST':
        title = request.form.get('title')
        status = request.form.get('status')
        file = request.files.get('file')
        
        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # Додаємо таймстемп, щоб уникнути однакових назв
            filename = f"{datetime.now().timestamp()}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_game = Game(title=title, status=status, file_name=filename, owner=current_user)
        db.session.add(new_game)
        db.session.commit()
        
        flash(f'Гру "{title}" додано до твоєї бібліотеки!', 'success')
        return redirect(url_for('my_library'))
        
    user_games = Game.query.filter_by(user_id=current_user.id).order_by(Game.date_added.desc()).all()
    return render_template('my_library.html', games=user_games)

@app.route('/delete_game/<int:game_id>', methods=['POST'])
@login_required
def delete_game(game_id):
    game = Game.query.get_or_404(game_id)
    if game.owner != current_user:
        flash('У вас немає прав для видалення цієї гри.', 'error')
        return redirect(url_for('my_library'))
    
    # Видаляємо файл з диска, якщо він є
    if game.file_name:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], game.file_name)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(game)
    db.session.commit()
    flash(f'Гру "{game.title}" видалено з бібліотеки.', 'success')
    return redirect(url_for('my_library'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)