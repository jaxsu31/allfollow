import os
import time
import random
import logging
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired, FeedbackRequired
from dotenv import load_dotenv

load_dotenv()

# Render loglarında detaylı görmek için loglamayı açıyoruz
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# DİKKAT: Eğer elinde sağlam bir proxy yoksa burayı None bırak. 
# Kalitesiz proxy "Bağlantı Hatası"nın 1 numaralı sebebidir.
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
    
    # Instagram'ı kandırmak için en güncel cihaz ayarları
    cl.set_device_settings({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "Xiaomi",
        "device": "chiron",
        "model": "Mi MIX 2",
        "cpu": "qcom",
        "version_code": "442431182"
    })

    if PROXY_URL:
        cl.set_proxy(PROXY_URL)
        logging.info(f"Proxy kullanılıyor: {PROXY_URL}")

    active_sessions[u] = cl
    
    try:
        logging.info(f"Giriş deneniyor: {u}")
        # İnsan gibi davranmak için rastgele bekleme
        time.sleep(random.uniform(2, 4))
        
        if cl.login(u, p):
            logging.info(f"Giriş Başarılı: {u}")
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
        logging.warning("Challenge (Onay) gerekiyor.")
        return jsonify(status="challenge", next_step="verify")
    except FeedbackRequired:
        return jsonify(status="error", message="Instagram geçici engel koydu. 30 dk sonra deneyin.")
    except Exception as e:
        err_msg = str(e).lower()
        logging.error(f"Hata Detayı: {err_msg}")
        
        if "checkpoint" in err_msg:
            return jsonify(status="challenge", next_step="verify")
        if "proxy" in err_msg:
            return jsonify(status="error", message="Proxy hatası! Proxy ayarlarını kontrol et.")
        
        return jsonify(status="error", message="Instagram Bağlantıyı Reddetti. (Sunucu IP'si Engelli olabilir)")

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
    except Exception as e:
        return jsonify(status="error", message="Kod hatalı: " + str(e))

# --- UI (SADE VE GÜÇLÜ) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #000; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; font-family: sans-serif; }
        .box { background: #111; border: 1px solid #333; padding: 2rem; border-radius: 1.5rem; width: 100%; max-width: 320px; }
        .page { display: none; } .active { display: block; }
        input { width: 100%; background: #222; border: 1px solid #444; padding: 0.8rem; border-radius: 0.5rem; color: #fff; margin-bottom: 1rem; outline: none; }
        button { width: 100%; background: #a855f7; color: #fff; font-weight: bold; padding: 0.8rem; border-radius: 0.5rem; border: none; cursor: pointer; }
        .loader { border: 2px solid #f3f3f3; border-top: 2px solid #a855f7; border-radius: 50%; width: 14px; height: 14px; animation: spin 1s linear infinite; display: inline-block; margin-right: 5px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div id="login-page" class="page active box">
        <h2 style="color:#a855f7; margin-bottom:1.5rem; font-weight:900;">ALLFOLLOW</h2>
        <input id="u" placeholder="Kullanıcı Adı">
        <input id="p" type="password" placeholder="Şifre">
        <button onclick="doLogin()" id="btn">GİRİŞ YAP</button>
        <p id="err" style="color:#ff4444; font-size:11px; margin-top:10px;"></p>
    </div>

    <div id="verify-page" class="page box">
        <h2 style="color:#f59e0b; margin-bottom:1rem;">Kod Onayı</h2>
        <input id="vcode" placeholder="000000" style="text-align:center; letter-spacing:4px;">
        <button onclick="doVerify()" id="vbtn" style="background:#f59e0b;">ONAYLA</button>
    </div>

    <div id="dashboard-page" class="page box" style="border-top: 4px solid #22c55e;">
        <h2 style="color:#22c55e;">Başarılı! ✅</h2>
        <p id="usr" style="margin-top:10px; font-weight:bold;"></p>
    </div>

    <script>
        async function doLogin() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn'), err = document.getElementById('err');
            btn.disabled = true; btn.innerHTML = '<div class="loader"></div> BAĞLANIYOR...';
            try {
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                if(d.status === "success") {
                    document.getElementById('usr').innerText = "@" + u;
                    showPage('dashboard-page');
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

        async function doVerify() {
            const code = document.getElementById('vcode').value, u = document.getElementById('u').value;
            const btn = document.getElementById('vbtn');
            btn.disabled = true;
            const r = await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
            const d = await r.json();
            if(d.status === "success") {
                showPage('dashboard-page');
            } else { alert(d.message); btn.disabled = false; }
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
