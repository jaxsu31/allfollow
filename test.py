import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# --- 1. AYARLAR ---
app = Flask(__name__)
app.secret_key = "all_follow_v30_exclusive"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v30.db"
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

# --- 3. MARKET ---
PACKAGES = [
    {"n": "100 Takipçi", "c": 800}, {"n": "200 Takipçi", "c": 1600},
    {"n": "300 Takipçi", "c": 2400}, {"n": "400 Takipçi", "c": 3200},
    {"n": "500 Takipçi", "c": 4000}, {"n": "1000 Takipçi", "c": 8000},
    {"n": "5000 Takipçi", "c": 40000}
]

# --- 4. GİRİŞ MANTIĞI ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # Instagram'ın 'yabancı cihaz' uyarısını aşmak için senin cihazını simüle ediyoruz
    cl.set_device({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "device": "TECNO KH7n",
        "cpu": "mt6765",
        "version_code": "444435623"
    })
    cl.set_locale("tr_TR")
    cl.set_country("TR")

    try:
        cl.login(u, p)
        login_ok = True
    except Exception as e:
        err = str(e).lower()
        if "challenge" in err or "checkpoint" in err:
            return jsonify(status="error", msg="Onay Gerekiyor! Instagram uygulamasını aç, 'BENDİM' de ve sonra tekrar Giriş Yap'a bas.")
        return jsonify(status="error", msg="Instagram girişi reddetti. Şifreyi kontrol edip 5 dk sonra deneyin.")

    if login_ok:
        user = User.query.filter_by(username=u).first()
        if not user:
            user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:6].upper(), device_data=json.dumps(cl.get_settings()))
            db.session.add(user)
        session['user'] = u
        db.session.commit()
        return jsonify(status="success")

# --- 5. PANEL VE ADMİN ROTALARI ---
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
    db.session.add(Ticket(username=session['user'], message=msg))
    db.session.commit()
    return jsonify(status="success", msg="İletildi!")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# Admin Paneli
@app.route('/admin')
def admin_gate(): return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/api/admin-login', methods=['POST'])
def api_admin_login():
    if request.form.get('u') == 'admin123' and request.form.get('p') == 'admin':
        session['admin_logged_in'] = True
        return redirect('/admin/dashboard')
    return "Hata!"

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'): return redirect('/admin')
    return render_template_string(ADMIN_DASH_HTML, orders=Order.query.all(), tickets=Ticket.query.all())

@app.route('/api/admin-reply', methods=['POST'])
def admin_reply():
    t = Ticket.query.get(request.form.get('id'))
    if t: t.reply = request.form.get('reply'); db.session.commit()
    return redirect('/admin/dashboard')

# --- 6. TASARIMLAR (HTML) ---
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>AllFollow | Giriş</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-sm p-10 bg-zinc-900 rounded-[3rem] border border-white/5">
        <h1 class="text-center font-black italic text-2xl mb-8 uppercase tracking-tighter">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="space-y-4">
            <input type="text" id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-black border border-white/10 p-5 rounded-2xl text-sm outline-none focus:border-teal-500">
            <input type="password" id="p" placeholder="Şifre" class="w-full bg-black border border-white/10 p-5 rounded-2xl text-sm outline-none focus:border-teal-500">
            <button onclick="login()" id="lbtn" class="w-full bg-teal-600 py-5 rounded-2xl font-black text-xs uppercase tracking-widest active:scale-95 transition-all">Giriş Yap</button>
            <p id="msg" class="text-center text-[10px] text-yellow-500 uppercase mt-4 font-bold"></p>
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
<head><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"><title>Panel</title></head>
<body class="bg-[#050505] text-zinc-400 pb-24 font-sans">
    <nav class="p-6 border-b border-white/5 flex justify-between bg-black sticky top-0 z-50">
        <div class="flex items-center gap-3"><h1 class="text-white font-black italic">ALLFOLLOW</h1><span class="text-[10px] bg-zinc-800 px-2 py-1 rounded">@{{ user.username }}</span></div>
        <div class="flex items-center gap-4"><div class="bg-zinc-900 px-4 py-2 rounded-2xl border border-teal-500/20 text-white font-bold text-xs"><i class="fa-solid fa-coins text-yellow-500 mr-2"></i>{{ user.coins }}</div><a href="/logout" class="text-zinc-500"><i class="fa-solid fa-power-off"></i></a></div>
    </nav>
    <div class="flex overflow-x-auto bg-zinc-900/50 sticky top-[73px] z-40 border-b border-white/5">
        <button onclick="tab('market')" class="px-8 py-5 text-[10px] font-bold uppercase tracking-widest">Market</button>
        <button onclick="tab('support')" class="px-8 py-5 text-[10px] font-bold uppercase tracking-widest">Destek</button>
        <button onclick="window.location.href='/logout'" class="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-teal-500">+ Hesap Ekle</button>
    </div>
    <main class="max-w-4xl mx-auto p-6">
        <div id="market" class="tab active grid grid-cols-1 sm:grid-cols-2 gap-4">
            {% for p in packages %}
            <div onclick="buy('{{p.n}}', {{p.c}})" class="bg-zinc-900/50 p-8 rounded-[2.5rem] border border-white/5 hover:border-teal-500/50 transition-all cursor-pointer">
                <h3 class="text-white font-bold">{{ p.n }}</h3>
                <p class="text-[10px] text-teal-500 mt-2 font-black uppercase">{{ p.c }} COIN</p>
            </div>
            {% endfor %}
        </div>
        <div id="support" class="tab hidden space-y-6">
            <textarea id="sup-msg" class="w-full bg-zinc-900 border border-white/10 rounded-2xl p-6 text-sm h-40 outline-none text-white focus:border-teal-500" placeholder="Sorununuzu yazın..."></textarea>
            <button onclick="sendSupport()" class="w-full bg-teal-600 py-5 rounded-2xl font-black text-[10px] uppercase tracking-widest">Gönder</button>
            {% for t in tickets %}<div class="bg-zinc-900/30 p-6 rounded-3xl border border-white/5"><p class="text-xs text-zinc-200">{{ t.message }}</p>{% if t.reply %}<p class="text-[10px] text-teal-500 mt-4 font-bold italic">Admin: {{ t.reply }}</p>{% endif %}</div>{% endfor %}
        </div>
    </main>
    <script>
        function tab(id){document.querySelectorAll('.tab').forEach(t=>t.classList.add('hidden'));document.getElementById(id).classList.remove('hidden');}
        async function buy(p,c){const target=prompt(p+" için hedef kullanıcı?");if(!target)return;const r=await fetch('/api/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({package:p,cost:c,target:target})});const d=await r.json();alert(d.msg);if(d.status==='success')location.reload();}
        async function sendSupport(){const m=document.getElementById('sup-msg').value;if(!m)return;await fetch('/api/support',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg:m})});location.reload();}
    </script>
</body>
</html>
"""

ADMIN_LOGIN_HTML = """<body style="background:#000; color:#fff; display:flex; align-items:center; justify-content:center; height:100vh; font-family:sans-serif;"><form action="/api/admin-login" method="post" style="background:#111; padding:40px; border-radius:30px; border:1px solid #333;"><h2 style="color:teal; text-align:center; margin-bottom:20px; font-weight:900;">ADMİN</h2><input name="u" placeholder="Admin" style="display:block; width:100%; margin-bottom:10px; padding:15px; background:#000; border:1px solid #333; color:#fff; border-radius:10px;"><input name="p" type="password" placeholder="Sifre" style="display:block; width:100%; margin-bottom:20px; padding:15px; background:#000; border:1px solid #333; color:#fff; border-radius:10px;"><button style="width:100%; padding:15px; background:teal; color:#fff; border:none; font-weight:bold; border-radius:10px; cursor:pointer;">GİRİŞ</button></form></body>"""

ADMIN_DASH_HTML = """
<!DOCTYPE html>
<html>
<head><script src="https://cdn.tailwindcss.com"></script><title>Admin Dashboard</title></head>
<body class="bg-black text-white p-10">
    <h1 class="text-3xl font-black italic mb-10">ALLFOLLOW <span class="text-teal-500">PANEL</span></h1>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-10">
        <div class="bg-zinc-900 p-8 rounded-3xl border border-white/5">
            <h2 class="text-teal-500 font-bold mb-6 italic">SİPARİŞLER</h2>
            {% for o in orders %}<div class="text-[10px] border-b border-white/5 py-3"><span class="text-white font-bold">@{{o.username}}</span> -> <span class="text-teal-400">@{{o.target_username}}</span> ({{o.package}})</div>{% endfor %}
        </div>
        <div class="bg-zinc-900 p-8 rounded-3xl border border-white/5">
            <h2 class="text-yellow-500 font-bold mb-6 italic">DESTEK</h2>
            {% for t in tickets %}
            <div class="bg-black/50 p-4 rounded-2xl mb-4 text-[10px]">
                <p class="font-bold mb-2">@{{t.username}}: {{t.message}}</p>
                <form action="/api/admin-reply" method="post" class="flex gap-2">
                    <input name="id" type="hidden" value="{{t.id}}">
                    <input name="reply" placeholder="Cevap yaz..." class="bg-zinc-800 border-none p-2 flex-1 text-white">
                    <button class="bg-teal-600 px-4 rounded font-bold">OK</button>
                </form>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
