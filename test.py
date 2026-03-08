import random
from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from instagrapi import Client

# --- UYGULAMA YAPILANDIRMASI ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///all_follow_final.db'
app.config['SECRET_KEY'] = 'all-follow-ultra-secret-key-2026'
db = SQLAlchemy(app)

# --- LOGIN YÖNETİCİSİ ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- PROXY LİSTESİ (Senin Sağladıkların) ---
PROXY_LIST = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73263145:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-84639863:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68182545:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-51767287:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68467738:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-96271173:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-74157191:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-58918651:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
]

# --- VERİTABANI MODELLERİ ---
class Customer(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    coins = db.Column(db.Integer, default=0)
    bots = db.relationship('InstagramBot', backref='owner', lazy=True)

class InstagramBot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    insta_username = db.Column(db.String(80), nullable=False)
    insta_password = db.Column(db.String(80), nullable=False)
    proxy_url = db.Column(db.String(255))
    status = db.Column(db.String(20), default="Pasif")
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return Customer.query.get(int(user_id))

# --- YOLLAR (ROUTES) ---

@app.route('/')
def home():
    return "<h1>All Follow API Aktif</h1><p><a href='/dashboard'>Panele Git</a></p>"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        if not Customer.query.filter_by(username=user).first():
            new_cust = Customer(username=user, password=pw)
            db.session.add(new_cust)
            db.session.commit()
            flash("Kayıt başarılı! Giriş yapabilirsiniz.", "success")
            return redirect(url_for('login'))
    return '''
        <form method="post">
            <input type="text" name="username" placeholder="Username" required><br>
            <input type="password" name="password" placeholder="Password" required><br>
            <button type="submit">Kayıt Ol</button>
        </form>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Customer.query.filter_by(username=request.form.get('username')).first()
        if user and user.password == request.form.get('password'):
            login_user(user)
            return redirect(url_for('dashboard'))
    return '''
        <form method="post">
            <input type="text" name="username" placeholder="Username" required><br>
            <input type="password" name="password" placeholder="Password" required><br>
            <button type="submit">Giriş Yap</button>
        </form>
    '''

@app.route('/dashboard')
@login_required
def dashboard():
    my_bots = InstagramBot.query.filter_by(customer_id=current_user.id).all()
    return render_template_string(DASHBOARD_HTML, user=current_user, bots=my_bots)

@app.route('/add_bot', methods=['POST'])
@login_required
def add_bot():
    i_user = request.form.get('insta_user')
    i_pass = request.form.get('insta_pass')
    
    selected_proxy = random.choice(PROXY_LIST)
    
    # Instagram Giriş Testi (Opsiyonel: Hız için direkt ekleyebilirsin)
    new_bot = InstagramBot(
        insta_username=i_user, 
        insta_password=i_pass, 
        customer_id=current_user.id,
        proxy_url=selected_proxy,
        status="Aktif (Test Edilmedi)"
    )
    db.session.add(new_bot)
    db.session.commit()
    flash("Bot başarıyla eklendi ve proxy atandı!", "info")
    return redirect(url_for('dashboard'))

@app.route('/earn_coin/<int:bot_id>')
@login_required
def earn_coin(bot_id):
    bot = InstagramBot.query.get(bot_id)
    if bot.customer_id == current_user.id:
        # Burada gerçek instagrapi takip kodu çalışacak
        # Şimdilik simülasyon:
        current_user.coins += 5
        db.session.commit()
        flash(f"{bot.insta_username} üzerinden coin kasıldı!", "success")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- HTML TEMPLATE (Basitlik için kod içinde) ---
from flask import render_template_string
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>All Follow Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="d-flex justify-content-between">
            <h2>Hoş geldin, {{ user.username }}</h2>
            <a href="/logout" class="btn btn-danger">Çıkış Yap</a>
        </div>
        <div class="card p-3 my-3 bg-primary text-white">
            <h4>Mevcut Coin: {{ user.coins }}</h4>
        </div>
        
        <div class="row">
            <div class="col-md-4">
                <div class="card p-3">
                    <h5>Instagram Bot Ekle</h5>
                    <form action="/add_bot" method="post">
                        <input type="text" name="insta_user" class="form-control mb-2" placeholder="Insta Kullanıcı">
                        <input type="password" name="insta_pass" class="form-control mb-2" placeholder="Şifre">
                        <button class="btn btn-success w-100">Hesabı Bağla</button>
                    </form>
                </div>
            </div>
            <div class="col-md-8">
                <div class="card p-3">
                    <h5>Bağlı Botlarım</h5>
                    <table class="table">
                        <thead><tr><th>User</th><th>Proxy</th><th>Durum</th><th>İşlem</th></tr></thead>
                        <tbody>
                            {% for bot in bots %}
                            <tr>
                                <td>{{ bot.insta_username }}</td>
                                <td>Aktif (Residential)</td>
                                <td>{{ bot.status }}</td>
                                <td><a href="/earn_coin/{{bot.id}}" class="btn btn-sm btn-warning">Coin Kas</a></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

# --- BAŞLATMA ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
