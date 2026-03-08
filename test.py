import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v17_ultra_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v17.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800)
    ref_code = db.Column(db.String(20), unique=True)
    last_daily_bonus = db.Column(db.String(20), default="")
    is_following_official = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    package = db.Column(db.String(100))
    cost = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=db.func.now())

# --- PROXY LİSTESİ (Örnek - Buraya 50 IP'ni ekleyebilirsin) ---
PROXY_LIST = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
]

# --- HTML TASARIMLARI ---

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head><title>All Follow | Giriş</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-sm p-8 bg-zinc-900 rounded-[2rem] border border-white/5 mx-4">
        <h2 class="text-2xl font-black mb-6 text-center italic text-teal-500">ALLFOLLOW</h2>
        <div class="space-y-4">
            <div id="login-fields">
                <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm mt-2 outline-none">
            </div>
            <div id="verify-fields" class="hidden">
                <input id="code" placeholder="000000" class="w-full bg-zinc-800 border border-teal-500 p-4 rounded-xl text-center text-2xl tracking-[0.5em] outline-none">
            </div>
            <button onclick="handleProcess()" id="btn" class="w-full bg-teal-600 py-4 rounded-xl font-black uppercase text-sm">Giriş Yap</button>
            <p id="msg" class="text-[10px] text-center text-yellow-500 mt-4"></p>
        </div>
    </div>
    <script>
        let isChallenge = false;
        async function handleProcess() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value, code = document.getElementById('code').value;
            const btn = document.getElementById('btn'), msg = document.getElementById('msg');
            btn.disabled = true; btn.innerText = "Yükleniyor...";
            const url = isChallenge ? '/api/verify' : '/api/login';
            try {
                const r = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({u, p, code}) });
                const d = await r.json();
                msg.innerText = d.msg;
                if (d.status === "challenge") {
                    isChallenge = true;
                    document.getElementById('login-fields').classList.add('hidden');
                    document.getElementById('verify-fields').classList.remove('hidden');
                } else if (d.status === "success") { window.location.href = "/panel"; }
            } catch(e) { msg.innerText = "Hata!"; }
            btn.disabled = false; btn.innerText = isChallenge ? "ONAYLA" : "GİRİŞ YAP";
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
    <style>.tab { display: none; } .active { display: block; }</style>
</head>
<body class="bg-[#050505] text-zinc-400 font-sans pb-20">
    <nav class="p-6 border-b border-white/5 flex justify-between items-center bg-black">
        <h1 class="text-white font-black italic">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="bg-zinc-900 px-4 py-2 rounded-xl border border-teal-500/20 text-white font-bold text-sm">
            <i class="fa-solid fa-coins text-yellow-500 mr-2"></i>{{ user.coins }}
        </div>
    </nav>

    <div class="flex border-b border-white/5 bg-zinc-900/50 sticky top-0 overflow-x-auto">
        <button onclick="tab('market')" class="px-6 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max border-b-2 border-transparent hover:text-white">Market</button>
        <button onclick="tab('tasks')" class="px-6 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max border-b-2 border-transparent hover:text-white">Görevler</button>
        <button onclick="tab('referral')" class="px-6 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max border-b-2 border-transparent hover:text-white">Referans</button>
        <button onclick="tab('support')" class="px-6 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max border-b-2 border-transparent hover:text-white">Destek</button>
    </div>

    <main class="p-6 max-w-4xl mx-auto">
        <div id="market" class="tab active grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div onclick="buy('100 Takipçi', 800)" class="bg-zinc-900 p-6 rounded-3xl border border-white/5 hover:border-teal-500 cursor-pointer">
                <h3 class="text-white font-bold">100 Takipçi</h3><p class="text-xs text-teal-500">800 COIN</p>
            </div>
            <div onclick="buy('1000 Takipçi', 8000)" class="bg-zinc-900 p-6 rounded-3xl border border-white/5 hover:border-teal-500 cursor-pointer">
                <h3 class="text-white font-bold">1000 Takipçi</h3><p class="text-xs text-teal-500">8.000 COIN</p>
            </div>
        </div>

        <div id="tasks" class="tab text-center py-10">
            <div class="bg-zinc-900 p-10 rounded-[2.5rem] border border-white/5">
                <i class="fa-solid fa-bolt text-4xl text-teal-500 mb-4"></i>
                <h3 class="text-white font-bold mb-4">Otomatik Coin Kasma</h3>
                <button class="bg-white text-black px-8 py-4 rounded-xl font-bold uppercase text-[10px]">Sistemi Başlat</button>
            </div>
        </div>

        <div id="referral" class="tab text-center py-10">
            <h3 class="text-white font-bold mb-4">Referans Kodun</h3>
            <div class="bg-black p-4 rounded-xl border border-dashed border-teal-500/50 text-teal-500 font-mono text-2xl">
                {{ user.ref_code }}
            </div>
        </div>
        
        <div id="support" class="tab">
            <textarea class="w-full bg-zinc-900 border border-white/10 p-4 rounded-xl text-sm h-32" placeholder="Sorununuz nedir?"></textarea>
            <button class="w-full bg-teal-600 py-4 rounded-xl mt-4 font-bold text-xs uppercase">Mesaj Gönder</button>
        </div>
    </main>

    <script>
        function tab(id) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active');
        }
        async function buy(p, c) {
            if(!confirm(p + " alınsın mı?")) return;
            const r = await fetch('/api/order', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({package:p, cost:c})});
            const d = await r.json(); alert(d.msg); if(d.status==="success") location.reload();
        }
    </script>
</body>
</html>
"""

# --- ROTALAR ---

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect(url_for('index'))
    user = User.query.filter_by(username=session['user']).first()
    return render_template_string(PANEL_HTML, user=user)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    cl.set_proxy(random.choice(PROXY_LIST))
    cl.set_locale("tr_TR") # Konum Eşleştirme (TopFollow gibi)
    cl.set_country("TR")
    
    try:
        cl.login(u, p)
        login_ok = True
    except Exception as e:
        err = str(e).lower()
        if "checkpoint" in err or "challenge" in err:
            session['temp_u'] = u
            return jsonify(status="challenge", msg="Kod Gerekli!")
        login_ok = True if cl.user_id else False

    if login_ok:
        user = User.query.filter_by(username=u).first()
        if not user:
            user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:6].upper())
            db.session.add(user)
        db.session.commit()
        session['user'] = u
        return jsonify(status="success", msg="Giriş Başarılı!")
    return jsonify(status="error", msg="Hata!")

@app.route('/api/order', methods=['POST'])
def order():
    data = request.json
    user = User.query.filter_by(username=session['user']).first()
    if user.coins >= data['cost']:
        user.coins -= data['cost']
        db.session.add(Order(username=user.username, package=data['package'], cost=data['cost']))
        db.session.commit()
        return jsonify(status="success", msg="Sipariş Alındı! (24-48 Saat)")
    return jsonify(status="error", msg="Yetersiz Coin!")

@app.route('/admin')
def admin():
    # admin123 / admin girişi buraya eklenecek
    orders = Order.query.all()
    return f"Siparisler: {str([o.package for o in orders])}"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
