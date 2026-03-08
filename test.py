import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# --- 1. AYARLAR VE VERİTABANI ---
app = Flask(__name__)
app.secret_key = "all_follow_v16_pro_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v16.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Geçici depolama (Challenge/Kod doğrulama için)
challenge_storage = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800) # Yeni üyelere 800 Hediye
    ref_code = db.Column(db.String(20), unique=True)
    is_following_official = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    package_name = db.Column(db.String(100))
    cost = db.Column(db.Integer)
    status = db.Column(db.String(50), default="Beklemede")
    timestamp = db.Column(db.DateTime, default=db.func.now())

# --- SABİTLER ---
PACKAGES = [
    {"name": "100 Takipçi", "coins": 800},
    {"name": "200 Takipçi", "coins": 1600},
    {"name": "300 Takipçi", "coins": 2400},
    {"name": "400 Takipçi", "coins": 3200},
    {"name": "500 Takipçi", "coins": 4000},
    {"name": "1000 Takipçi", "coins": 8000},
    {"name": "5000 Takipçi", "coins": 40000},
]

# --- 2. ARAYÜZ TASARIMLARI (HTML) ---

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>All Follow | Giriş</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen font-sans">
    <div class="w-full max-w-sm p-8 bg-zinc-900 rounded-[2.5rem] border border-white/5 shadow-2xl mx-4">
        <h2 class="text-2xl font-black mb-6 text-center tracking-tighter italic">ALLFOLLOW<span class="text-teal-500">.</span></h2>
        
        <div class="space-y-4">
            <div id="login-fields">
                <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-2xl text-sm outline-none focus:border-teal-500 transition">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-2xl text-sm mt-2 outline-none focus:border-teal-500 transition">
            </div>

            <div id="verify-fields" class="hidden text-center">
                <p class="text-xs text-teal-400 mb-4 font-bold uppercase tracking-widest">Onay Kodu Gönderildi</p>
                <input id="code" placeholder="000000" class="w-full bg-zinc-800 border border-teal-500 p-4 rounded-2xl text-center text-2xl tracking-[0.5em] outline-none">
            </div>

            <button onclick="handleProcess()" id="btn" class="w-full bg-teal-600 py-4 rounded-2xl font-black uppercase text-sm hover:bg-teal-500 transition-all shadow-lg shadow-teal-900/20">GİRİŞ YAP</button>
            <p id="msg" class="text-[10px] text-center text-yellow-500 font-bold mt-4 min-h-[1rem] uppercase tracking-wider"></p>
        </div>
    </div>

    <script>
        let isChallenge = false;
        async function handleProcess() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value, 
                  code = document.getElementById('code').value, btn = document.getElementById('btn'), msg = document.getElementById('msg');
            if (!u || !p) { msg.innerText = "Bilgileri giriniz!"; return; }
            btn.disabled = true; btn.innerText = "BAĞLANILIYOR...";
            
            const url = isChallenge ? '/api/verify' : '/api/login';
            const body = isChallenge ? { u, code } : { u, p };

            try {
                const r = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
                const d = await r.json();
                msg.innerText = d.msg;
                if (d.status === "challenge") {
                    isChallenge = true;
                    document.getElementById('login-fields').classList.add('hidden');
                    document.getElementById('verify-fields').classList.remove('hidden');
                    btn.innerText = "KODU ONAYLA";
                } else if (d.status === "success") {
                    setTimeout(() => window.location.href = "/panel", 1000);
                }
            } catch(e) { msg.innerText = "Sunucu Hatası!"; } finally { btn.disabled = false; if(!isChallenge) btn.innerText = "GİRİŞ YAP"; }
        }
    </script>
</body>
</html>
"""

PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <title>All Follow | Panel</title>
</head>
<body class="bg-[#050505] text-zinc-400 font-sans">
    <nav class="border-b border-white/5 p-6 flex justify-between items-center sticky top-0 bg-black/80 backdrop-blur-lg z-50">
        <h1 class="text-white font-black tracking-tighter text-2xl italic">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="flex gap-4 items-center">
            <div class="bg-zinc-900 border border-teal-500/20 px-4 py-2 rounded-2xl flex items-center gap-2">
                <i class="fa-solid fa-coins text-yellow-500 animate-pulse"></i>
                <span class="text-white font-bold">{{ user.coins }}</span>
            </div>
            <a href="/logout" class="text-[10px] font-black uppercase tracking-widest hover:text-white transition">Çıkış</a>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto p-6 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div class="md:col-span-2 space-y-6">
            <h3 class="text-white font-bold flex items-center gap-2 uppercase text-xs tracking-[0.2em]"><i class="fa-solid fa-shop text-teal-500"></i> Market</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {% for pkg in packages %}
                <div onclick="order('{{ pkg.name }}')" class="bg-zinc-900/50 border border-white/5 p-8 rounded-[2.5rem] hover:border-teal-500 transition-all cursor-pointer group hover:bg-zinc-900">
                    <h4 class="text-white font-bold group-hover:text-teal-500 transition text-lg">{{ pkg.name }}</h4>
                    <p class="text-[10px] uppercase tracking-widest mt-2 text-zinc-500">Fiyat: {{ pkg.coins }} Coin</p>
                </div>
                {% endfor %}
            </div>
        </div>
        <div class="space-y-6">
            <div class="bg-zinc-900/50 border border-white/5 p-8 rounded-[2.5rem]">
                <h4 class="text-white font-bold mb-4 text-xs uppercase tracking-widest">Referans Sistemi</h4>
                <div class="bg-black p-4 rounded-2xl border border-teal-500/20 text-center">
                    <span class="text-teal-500 font-mono font-bold">{{ user.ref_code }}</span>
                </div>
                <p class="text-[10px] mt-4 leading-relaxed">Arkadaşlarını davet et, her girişte coin kazan!</p>
            </div>
        </div>
    </main>
    <script>
        async function order(name) {
            if(!confirm(name + " satın alınsın mı?")) return;
            const r = await fetch('/api/order', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({package:name}) });
            const d = await r.json();
            alert(d.msg);
            if(d.status === "success") location.reload();
        }
    </script>
</body>
</html>
"""

MUST_FOLLOW_HTML = """
<body class="bg-black text-white flex items-center justify-center h-screen font-sans">
    <div class="text-center p-12 bg-zinc-900 rounded-[3rem] border border-teal-500/20 max-w-sm mx-4">
        <div class="w-20 h-20 bg-teal-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <i class="fa-brands fa-instagram text-teal-500 text-3xl"></i>
        </div>
        <h2 class="text-2xl font-black mb-4 tracking-tighter italic">DUR YOLCU!</h2>
        <p class="text-zinc-500 text-sm mb-8 leading-relaxed">Sistemi kullanabilmek için resmi Instagram hesabımızı takip etmelisin.</p>
        <a href="https://instagram.com/allfollow_resmi" target="_blank" onclick="followed()" class="block w-full bg-teal-600 py-4 rounded-2xl font-black uppercase text-[10px] tracking-[0.2em] hover:bg-teal-500 transition shadow-xl shadow-teal-900/20">TAKİP ET VE ONAYLA</a>
    </div>
    <script>
        async function followed() {
            setTimeout(async () => {
                await fetch('/api/follow_official', {method:'POST'});
                location.reload();
            }, 4000);
        }
    </script>
</body>
"""

# --- 3. API ROTALARI ---

@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    # Örnek Proxy (Kendi listenizi buraya ekleyin)
    cl.set_proxy("http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959")
    
    try:
        cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "device": "Samsung Galaxy S9"})
        cl.login(u, p)
        login_success = True
    except Exception as e:
        err = str(e).lower()
        if "checkpoint" in err or "challenge" in err:
            challenge_storage[u] = {"client": cl}
            return jsonify(status="challenge", msg="Doğrulama kodu gerekli!")
        login_success = True if cl.user_id else False

    if login_success:
        user = User.query.filter_by(username=u).first()
        if not user:
            user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:8])
            db.session.add(user)
        db.session.commit()
        session['user'] = u
        return jsonify(status="success", msg="Giriş Başarılı!")
    return jsonify(status="error", msg="Instagram girişi reddetti.")

@app.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.json
    u, code = data.get('u'), data.get('code')
    if u in challenge_storage:
        try:
            challenge_storage[u]["client"].login(u, "", verification_code=code)
            session['user'] = u
            return jsonify(status="success", msg="Kod Onaylandı!")
        except: return jsonify(status="error", msg="Kod Hatalı!")
    return jsonify(status="error", msg="Oturum Bulunamadı.")

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    user = User.query.filter_by(username=session['user']).first()
    if not user.is_following_official: return render_template_string(MUST_FOLLOW_HTML)
    return render_template_string(PANEL_HTML, user=user, packages=PACKAGES)

@app.route('/api/follow_official', methods=['POST'])
def follow_official():
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
        user.is_following_official = True
        db.session.commit()
        return jsonify(status="success")
    return jsonify(status="error")

@app.route('/api/order', methods=['POST'])
def place_order():
    if 'user' not in session: return jsonify(status="error")
    data = request.json
    user = User.query.filter_by(username=session['user']).first()
    pkg = next((p for p in PACKAGES if p['name'] == data['package']), None)
    if user.coins >= pkg['coins']:
        user.coins -= pkg['coins']
        db.session.add(Order(username=user.username, package_name=pkg['name'], cost=pkg['coins']))
        db.session.commit()
        return jsonify(status="success", msg="Sipariş Alındı! (24-48 Saat)")
    return jsonify(status="error", msg="Yetersiz Coin!")

@app.route('/admin')
def admin_page():
    orders = Order.query.order_by(Order.timestamp.desc()).all()
    return f"<body style='background:#111;color:#eee;'><h2>Siparişler</h2>{str([(o.username, o.package_name) for o in orders])}</body>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
