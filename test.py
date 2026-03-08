import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v17_ultra_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v17.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 1. PROXY LİSTESİ (TÜM LİSTENİ BURAYA EKLE) ---
PROXY_LIST = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    # ... Diğer 48 proxy'ni buraya virgülle ayırarak ekleyebilirsin
]

# --- 2. VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800)
    ref_code = db.Column(db.String(20), unique=True)
    last_daily_bonus = db.Column(db.String(20), default="") # YYYY-MM-DD formatında
    is_following_official = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    package = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=db.func.now())

# --- 3. DASHBOARD TASARIMI (SEKMELİ YAPI) ---
PANEL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <title>AllFollow | Dashboard</title>
    <style>
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .tab-btn.active { border-bottom: 2px solid #14b8a6; color: white; }
    </style>
</head>
<body class="bg-[#050505] text-zinc-400 font-sans pb-24">

    <nav class="p-6 border-b border-white/5 flex justify-between items-center bg-black/50 backdrop-blur-md sticky top-0 z-50">
        <h1 class="text-white font-black italic tracking-tighter">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="bg-zinc-900 px-4 py-2 rounded-2xl border border-teal-500/20 flex items-center gap-2">
            <i class="fa-solid fa-coins text-yellow-500"></i>
            <span class="text-white font-bold" id="coin-count">{{ user.coins }}</span>
        </div>
    </nav>

    <div class="flex overflow-x-auto border-b border-white/5 bg-zinc-900/30 sticky top-[73px] z-40">
        <button onclick="openTab('market')" class="tab-btn active px-6 py-4 text-xs font-black uppercase tracking-widest min-w-max">Market</button>
        <button onclick="openTab('tasks')" class="tab-btn px-6 py-4 text-xs font-black uppercase tracking-widest min-w-max">Görevler</button>
        <button onclick="openTab('referral')" class="tab-btn px-6 py-4 text-xs font-black uppercase tracking-widest min-w-max">Referans</button>
        <button onclick="openTab('daily')" class="tab-btn px-6 py-4 text-xs font-black uppercase tracking-widest min-w-max">Bonus</button>
        <button onclick="openTab('support')" class="tab-btn px-6 py-4 text-xs font-black uppercase tracking-widest min-w-max">Destek</button>
    </div>

    <main class="max-w-4xl mx-auto p-6">
        
        <div id="market" class="tab-content active space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div onclick="buy(800, '100 Takipçi')" class="bg-zinc-900 p-6 rounded-3xl border border-white/5 hover:border-teal-500 transition">
                    <h3 class="text-white font-bold">100 Takipçi</h3>
                    <p class="text-[10px] mt-1 text-teal-500">800 COIN</p>
                </div>
                <div onclick="buy(8000, '1000 Takipçi')" class="bg-zinc-900 p-6 rounded-3xl border border-white/5 hover:border-teal-500 transition">
                    <h3 class="text-white font-bold">1000 Takipçi</h3>
                    <p class="text-[10px] mt-1 text-teal-500">8.000 COIN</p>
                </div>
            </div>
            <p class="text-[10px] text-center text-zinc-600 mt-4">Siparişler 24-48 saat içinde tamamlanır.</p>
        </div>

        <div id="tasks" class="tab-content space-y-4 text-center">
            <div class="bg-zinc-900 p-8 rounded-[2rem] border border-white/5">
                <i class="fa-solid fa-robot text-4xl text-teal-500 mb-4"></i>
                <h3 class="text-white font-bold">Otomatik Coin Kas</h3>
                <p class="text-xs mt-2 mb-6">Bot arka planda başkalarını takip ederek coin kazanır.</p>
                <button onclick="startMining()" id="mine-btn" class="bg-white text-black px-8 py-4 rounded-2xl font-black text-xs uppercase tracking-widest">Başlat</button>
            </div>
            <button class="w-full bg-zinc-900 p-4 rounded-xl text-xs font-bold border border-white/5">Hesap Ekle +</button>
        </div>

        <div id="referral" class="tab-content text-center">
            <div class="bg-zinc-900 p-8 rounded-[2rem] border border-white/5">
                <h3 class="text-white font-bold mb-4">Referans Kodun</h3>
                <div class="bg-black p-4 rounded-2xl border border-dashed border-teal-500/50 text-teal-500 font-mono text-xl">
                    {{ user.ref_code }}
                </div>
                <p class="text-xs mt-4">Bu kodu paylaşan her arkadaşın için 200 Coin kazanırsın!</p>
            </div>
        </div>

        <div id="daily" class="tab-content text-center">
            <div class="bg-zinc-900 p-8 rounded-[2rem] border border-white/5">
                <h3 class="text-white font-bold mb-2">Günlük Hediye</h3>
                <p class="text-xs mb-6 text-zinc-500">Her gün giriş yaparak 5 Coin al.</p>
                <button onclick="claimDaily()" class="bg-teal-600 text-white px-8 py-4 rounded-2xl font-black text-xs uppercase tracking-widest">Hediyeyi Al</button>
            </div>
        </div>

        <div id="support" class="tab-content">
            <div class="bg-zinc-900 p-8 rounded-[2rem] border border-white/5">
                <h3 class="text-white font-bold mb-4">Destek Talebi</h3>
                <textarea class="w-full bg-black border border-white/10 rounded-2xl p-4 text-sm outline-none mb-4" placeholder="Sorununuzu yazın..."></textarea>
                <button class="w-full bg-teal-600 py-4 rounded-xl text-xs font-black uppercase">Gönder</button>
            </div>
        </div>

    </main>

    <script>
        function openTab(id) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.currentTarget.classList.add('active');
        }

        async function claimDaily() {
            const r = await fetch('/api/daily-bonus', {method:'POST'});
            const d = await r.json();
            alert(d.msg);
            if(d.status === "success") location.reload();
        }

        async function buy(cost, name) {
            if(!confirm(name + " satın alınsın mı?")) return;
            const r = await fetch('/api/order', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({cost, package: name})
            });
            const d = await r.json();
            alert(d.msg);
            if(d.status === "success") location.reload();
        }
    </script>
</body>
</html>
"""

# --- 4. API VE BOT MANTIĞI ---

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # RASTGELE PROXY SEÇİMİ
    proxy = random.choice(PROXY_LIST)
    cl.set_proxy(proxy)
    
    # TOPFOLLOW MANTIĞI: KONUM VE CİHAZ EŞLEŞTİRME
    cl.set_device({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "device": "Samsung Galaxy S9",
        "model": "SM-G960F",
        "device_id": str(uuid.uuid4())
    })
    cl.set_locale("tr_TR") # Konumu Türkiye olarak gösterir
    cl.set_country("TR")

    try:
        cl.login(u, p)
        login_ok = True
    except Exception as e:
        err = str(e).lower()
        if "checkpoint" in err or "challenge" in err:
            challenge_storage[u] = {"client": cl}
            return jsonify(status="challenge", msg="Onay kodu gerekli!")
        login_ok = True if cl.user_id else False

    if login_ok:
        user = User.query.filter_by(username=u).first()
        if not user:
            user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:6].upper())
            db.session.add(user)
        db.session.commit()
        session['user'] = u
        return jsonify(status="success", msg="Giriş Başarılı!")
    
    return jsonify(status="error", msg="Giriş reddedildi. Şifreyi veya IP'yi kontrol et.")

@app.route('/api/daily-bonus', methods=['POST'])
def daily_bonus():
    user = User.query.filter_by(username=session['user']).first()
    today = time.strftime("%Y-%m-%d")
    if user.last_daily_bonus == today:
        return jsonify(status="error", msg="Bugün zaten bonus aldın!")
    
    user.coins += 5
    user.last_daily_bonus = today
    db.session.commit()
    return jsonify(status="success", msg="5 Coin hesabına eklendi!")

# ... (Diğer sipariş ve takip rotaları buraya gelecek) ...

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=10000)
