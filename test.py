import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, CheckpointRequired

# --- 1. PROJE BAŞLATMA ---
app = Flask(__name__)
app.secret_key = "all_follow_v25_final_gold"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v25.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- 2. MODELLER ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800)
    ref_code = db.Column(db.String(20), unique=True)
    device_data = db.Column(db.Text) 
    last_bonus = db.Column(db.String(20), default="")

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100)) 
    target_username = db.Column(db.String(100)) 
    package = db.Column(db.String(100))
    cost = db.Column(db.Integer)
    status = db.Column(db.String(50), default="Beklemede")
    timestamp = db.Column(db.DateTime, default=db.func.now())

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    message = db.Column(db.Text)
    reply = db.Column(db.Text, default="")

# --- 3. MARKET PAKETLERİ ---
PACKAGES = [
    {"n": "100 Takipçi", "c": 800}, {"n": "200 Takipçi", "c": 1600},
    {"n": "300 Takipçi", "c": 2400}, {"n": "400 Takipçi", "c": 3200},
    {"n": "500 Takipçi", "c": 4000}, {"n": "1000 Takipçi", "c": 8000},
    {"n": "5000 Takipçi", "c": 40000}
]

# --- 4. GİRİŞ VE ONAY MANTIĞI ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    existing_user = User.query.filter_by(username=u).first()
    if existing_user and existing_user.device_data:
        cl.set_settings(json.loads(existing_user.device_data))
    else:
        # Cihazı kilitliyoruz (TECNO KH7n simülasyonu)
        cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "device": "TECNO KH7n", "cpu": "mt6765"})
        cl.set_locale("tr_TR")
        cl.set_country("TR")

    try:
        cl.login(u, p)
        login_ok = True
    except (ChallengeRequired, CheckpointRequired):
        return jsonify(status="error", msg="Instagram'ı aç ve 'BENDİM' de, sonra buraya gelip tekrar giriş yap!")
    except Exception:
        return jsonify(status="error", msg="Bağlantı engellendi veya şifre yanlış.")

    if login_ok:
        if not existing_user:
            existing_user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:6].upper(), device_data=json.dumps(cl.get_settings()))
            db.session.add(existing_user)
        session['user'] = u
        db.session.commit()
        return jsonify(status="success")

# --- 5. PANEL ROTALARI ---
@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    user = User.query.filter_by(username=session['user']).first()
    tickets = Ticket.query.filter_by(username=user.username).all()
    return render_template_string(PANEL_HTML, user=user, packages=PACKAGES, tickets=tickets)

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json
    user = User.query.filter_by(username=session['user']).first()
    if user.coins >= data['cost']:
        user.coins -= data['cost']
        new_order = Order(username=user.username, target_username=data['target'], package=data['package'], cost=data['cost'])
        db.session.add(new_order)
        db.session.commit()
        return jsonify(status="success", msg="Sipariş Alındı!")
    return jsonify(status="error", msg="Yetersiz Coin!")

@app.route('/api/support', methods=['POST'])
def api_support():
    msg = request.json.get('msg')
    new_t = Ticket(username=session['user'], message=msg)
    db.session.add(new_t)
    db.session.commit()
    return jsonify(status="success", msg="İletildi!")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- 6. ADMİN BÖLÜMÜ ---
@app.route('/admin')
def admin_gate():
    return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/api/admin-login', methods=['POST'])
def api_admin_login():
    if request.form.get('u') == 'admin123' and request.form.get('p') == 'admin':
        session['admin_logged_in'] = True
        return redirect('/admin/dashboard')
    return "Hata!"

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'): return redirect('/admin')
    orders = Order.query.all()
    tickets = Ticket.query.all()
    return render_template_string(ADMIN_DASH_HTML, orders=orders, tickets=tickets)

@app.route('/api/admin-reply', methods=['POST'])
def admin_reply():
    tid = request.form.get('id')
    rep = request.form.get('reply')
    ticket = Ticket.query.get(tid)
    if ticket:
        ticket.reply = rep
        db.session.commit()
    return redirect('/admin/dashboard')

# --- TASARIMLAR (HTML) ---
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>Giriş</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-sm p-10 bg-zinc-900 rounded-[3rem] border border-white/5 shadow-2xl shadow-teal-500/5">
        <h1 class="text-center font-black italic text-2xl mb-8 tracking-tighter">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="space-y-4">
            <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-black border border-white/10 p-5 rounded-2xl text-sm outline-none focus:border-teal-500 transition-all duration-300">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-5 rounded-2xl text-sm outline-none focus:border-teal-500 transition-all duration-300">
            <button onclick="login()" id="lbtn" class="w-full bg-teal-600 hover:bg-teal-500 py-5 rounded-2xl font-black text-xs uppercase tracking-[0.2em] transition-all active:scale-95">Giriş Yap</button>
            <p id="msg" class="text-center text-[10px] text-yellow-500 uppercase font-bold mt-4"></p>
        </div>
    </div>
    <script>
        async function login() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('lbtn'), msg = document.getElementById('msg');
            btn.disabled = true; btn.innerText = "BAĞLANILIYOR...";
            const r = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({u, p}) });
            const d = await r.json();
            if(d.status === "success") window.location.href="/panel";
            else { msg.innerText = d.msg; btn.disabled = false; btn.innerText = "Giriş Yap"; }
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
    <title>AllFollow | Panel</title>
</head>
<body class="bg-[#050505] text-zinc-400 font-sans pb-24">
    <nav class="p-6 border-b border-white/5 flex justify-between bg-black sticky top-0 z-50 backdrop-blur-xl bg-black/80">
        <div class="flex items-center gap-3">
            <h1 class="text-white font-black italic tracking-tighter">ALLFOLLOW</h1>
            <span class="text-[10px] bg-zinc-800 px-2 py-1 rounded-lg text-zinc-500 font-bold border border-white/5 italic">@{{ user.username }}</span>
        </div>
        <div class="flex items-center gap-4">
            <div class="bg-zinc-900 px-4 py-2 rounded-2xl border border-teal-500/20 text-white font-bold text-xs flex items-center gap-2">
                <i class="fa-solid fa-coins text-yellow-500"></i>{{ user.coins }}
            </div>
            <a href="/logout" class="text-zinc-500 hover:text-red-500 transition-colors"><i class="fa-solid fa-power-off"></i></a>
        </div>
    </nav>

    <div class="flex overflow-x-auto bg-zinc-900/50 sticky top-[73px] z-40 border-b border-white/5 backdrop-blur-md">
        <button onclick="tab('market')" class="px-8 py-5 text-[10px] font-bold uppercase tracking-widest min-w-max hover:text-white transition-all">Market</button>
        <button onclick="tab('earn')" class="px-8 py-5 text-[10px] font-bold uppercase tracking-widest min-w-max hover:text-white transition-all">Coin Kas</button>
        <button onclick="tab('support')" class="px-8 py-5 text-[10px] font-bold uppercase tracking-widest min-w-max hover:text-white transition-all">Destek</button>
        <button onclick="window.location.href='/logout'" class="px-8 py-5 text-[10px] font-bold uppercase tracking-widest min-w-max text-teal-500 bg-teal-500/5">+ Hesap Ekle</button>
    </div>

    <main class="max-w-4xl mx-auto p-6">
        <div id="market" class="tab active grid grid-cols-1 sm:grid-cols-2 gap-4">
            {% for p in packages %}
            <div onclick="buy('{{p.n}}', {{p.c}})" class="bg-zinc-900/50 p-8 rounded-[2.5rem] border border-white/5 hover:border-teal-500/50 hover:bg-zinc-900 cursor-pointer transition-all duration-500 group">
                <h3 class="text-white font-bold group-hover:text-teal-400 transition-colors">{{ p.n }}</h3>
                <p class="text-[10px] text-teal-500 mt-2 font-black tracking-widest uppercase">{{ p.c }} COIN</p>
            </div>
            {% endfor %}
        </div>

        <div id="earn" class="tab hidden text-center space-y-6 py-12">
            <div class="w-24 h-24 bg-teal-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-teal-500/20">
                <i class="fa-solid fa-bolt-lightning text-teal-500 text-3xl animate-pulse"></i>
            </div>
            <h2 class="text-white font-black text-2xl italic">OTOMATİK HAVUZ</h2>
            <p class="text-xs text-zinc-500 max-w-xs mx-auto">Başkalarını takip ederek her işlem başına 4 Coin kazanabilirsin.</p>
            <button class="w-full max-w-xs bg-teal-600 py-5 rounded-2xl font-black text-[10px] uppercase tracking-widest shadow-lg shadow-teal-500/20">Sistemi Başlat</button>
        </div>

        <div id="support" class="tab hidden space-y-6">
            <div class="bg-zinc-900/50 p-8 rounded-[2.5rem] border border-white/5">
                <textarea id="sup-msg" class="w-full bg-black border border-white/10 rounded-2xl p-6 text-sm h-40 focus:border-teal-500 outline-none text-white transition-all" placeholder="Mesajınızı detaylıca yazın..."></textarea>
                <button onclick="sendSupport()" class="w-full bg-white text-black py-5 rounded-2xl font-black text-[10px] uppercase tracking-widest mt-4 hover:bg-teal-500 hover:text-white transition-all">Gönder</button>
            </div>
            <div class="space-y-3">
                {% for t in tickets %}
                <div class="bg-zinc-900/30 p-6 rounded-3xl border border-white/5">
                    <p class="text-xs text-zinc-200">{{ t.message }}</p>
                    {% if t.reply %}
                    <div class="mt-4 pt-4 border-t border-white/5 flex gap-3 items-start">
                        <div class="w-6 h-6 bg-teal-500 rounded-full flex-shrink-0 flex items-center justify-center text-[10px] text-black font-bold">A</div>
                        <p class="text-[10px] text-teal-500 font-medium italic">Admin: {{ t.reply }}</p>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
    </main>

    <script>
        function tab(id) {
            document.querySelectorAll('.tab').forEach(t => t.classList.add('hidden'));
            document.getElementById(id).classList.remove('hidden');
        }
        async function buy(p, c) {
            const target = prompt(p + " paketi hangi kullanıcı adına gönderilsin?");
            if(!target) return;
            const r = await fetch('/api/order', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({package:p, cost:c, target:target}) });
            const d = await r.json(); alert(d.msg); if(d.status==='success') location.reload();
        }
        async function sendSupport() {
            const m = document.getElementById('sup-msg').value;
            if(!m) return;
            const r = await fetch('/api/support', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({msg:m}) });
            const d = await r.json(); alert(d.msg); location.reload();
        }
    </script>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """
<body style="background:#000; color:#fff; display:flex; align-items:center; justify-content:center; height:100vh; font-family:sans-serif;">
    <form action="/api/admin-login" method="post" style="background:#111; padding:40px; border-radius:30px; border:1px solid #333; width:300px;">
        <h2 style="color:teal; text-align:center; margin-bottom:20px; font-weight:900;">ADMİN GİRİŞİ</h2>
        <input name="u" placeholder="Kullanıcı Adı" style="display:block; width:100%; margin-bottom:10px; padding:15px; background:#000; border:1px solid #333; color:#fff; border-radius:10px;">
        <input name="p" type="password" placeholder="Şifre" style="display:block; width:100%; margin-bottom:20px; padding:15px; background:#000; border:1px solid #333; color:#fff; border-radius:10px;">
        <button style="width:100%; padding:15px; background:teal; color:#fff; border:none; font-weight:bold; cursor:pointer; border-radius:10px;">GİRİŞ YAP</button>
    </form>
</body>
"""

ADMIN_DASH_HTML = """
<!DOCTYPE html>
<html>
<head><script src="https://cdn.tailwindcss.com"></script><title>Admin Panel</title></head>
<body class="bg-black text-white p-10 font-sans">
    <div class="max-w-6xl mx-auto flex justify-between items-center mb-10">
        <h1 class="text-3xl font-black italic">YÖNETİM <span class="text-teal-500 text-sm">v25</span></h1>
        <a href="/logout" class="bg-red-500/10 text-red-500 px-6 py-2 rounded-xl text-xs font-bold border border-red-500/20">Çıkış</a>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-10">
        <div class="bg-zinc-900 p-8 rounded-[2rem] border border-white/5">
            <h2 class="text-teal-500 font-black mb-6 flex items-center gap-2"><i class="fa-solid fa-shopping-cart"></i> SİPARİŞLER</h2>
            <div class="space-y-3 overflow-y-auto max-h-[500px] pr-2">
                {% for o in orders %}
                <div class="bg-black/50 p-4 rounded-2xl border border-white/5 text-[11px] flex justify-between items-center">
                    <div>
                        <p class="text-zinc-500">Alıcı: <span class="text-white font-bold">@{{ o.username }}</span></p>
                        <p class="text-teal-500">Hedef: <span class="text-teal-400 font-bold uppercase">@{{ o.target_username }}</span></p>
                    </div>
                    <div class="text-right">
                        <p class="text-white font-black">{{ o.package }}</p>
                        <p class="text-zinc-600">{{ o.timestamp.strftime('%H:%M') }}</p>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="bg-zinc-900 p-8 rounded-[2rem] border border-white/5">
            <h2 class="text-yellow-500 font-black mb-6 flex items-center gap-2"><i class="fa-solid fa-headset"></i> DESTEK TALEPLERİ</h2>
            <div class="space-y-4">
                {% for t in tickets %}
                <div class="bg-black/50 p-6 rounded-2xl border border-white/5">
                    <div class="flex justify-between items-center mb-3">
                        <span class="text-xs font-bold text-white">@{{ t.username }}</span>
                        <span class="text-[9px] bg-zinc-800 px-2 py-1 rounded text-zinc-500 uppercase">{{ 'CEVAPLANDI' if t.reply else 'BEKLEMEDE' }}</span>
                    </div>
                    <p class="text-[11px] text-zinc-400 leading-relaxed mb-4">{{ t.message }}</p>
                    <form action="/api/admin-reply" method="post" class="flex gap-2">
                        <input name="id" type="hidden" value="{{ t.id }}">
                        <input name="reply" placeholder="Cevabınızı yazın..." class="bg-black border border-white/10 p-3 rounded-xl text-[10px] flex-1 text-white outline-none focus:border-teal-500">
                        <button class="bg-teal-600 px-4 rounded-xl text-[10px] font-bold">GÖNDER</button>
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
