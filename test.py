import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v18_final_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v18.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800)
    ref_code = db.Column(db.String(20), unique=True)
    device_data = db.Column(db.Text) # Cihaz ID ve Konum Sabitleme
    is_following_official = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100)) # Siparişi veren
    target_username = db.Column(db.String(100)) # Takipçi gidecek hesap
    package = db.Column(db.String(100))
    cost = db.Column(db.Integer)
    status = db.Column(db.String(50), default="Beklemede")
    timestamp = db.Column(db.DateTime, default=db.func.now())

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    message = db.Column(db.Text)
    reply = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="Açık")

# --- SABİTLER ---
PACKAGES = [
    {"n": "100 Takipçi", "c": 800}, {"n": "200 Takipçi", "c": 1600},
    {"n": "300 Takipçi", "c": 2400}, {"n": "400 Takipçi", "c": 3200},
    {"n": "500 Takipçi", "c": 4000}, {"n": "1000 Takipçi", "c": 8000},
    {"n": "5000 Takipçi", "c": 40000}
]

# --- ROTALAR ---

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # Konum ve Cihaz Sabitleme
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
        # "Bu siz misiniz?" veya "Onay Kodu" kontrolü
        if "checkpoint" in err or "challenge" in err:
            if "select_verify_method" in err or "choice" in err:
                return jsonify(status="error", msg="Instagram'a gir ve 'Bendim' butonuna bas, sonra tekrar dene!")
            return jsonify(status="challenge", msg="Doğrulama kodu gerekli!")
        login_ok = True if cl.user_id else False

    if login_ok:
        if not existing_user:
            new_user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:6].upper(), device_data=json.dumps(cl.get_settings()))
            db.session.add(new_user)
        session['user'] = u
        db.session.commit()
        return jsonify(status="success", msg="Giriş Başarılı!")
    
    return jsonify(status="error", msg="Giriş reddedildi. Şifrenizi kontrol edin.")

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
        return jsonify(status="success", msg="Sipariş Alındı! 24-48 Saat İçinde Tamamlanacaktır.")
    return jsonify(status="error", msg="Yetersiz Coin!")

@app.route('/api/support', methods=['POST'])
def support():
    msg = request.json.get('msg')
    new_t = Ticket(username=session['user'], message=msg)
    db.session.add(new_t)
    db.session.commit()
    return jsonify(status="success", msg="Mesaj iletildi!")

# --- ADMİN PANELİ ---
@app.route('/admin')
def admin_login():
    return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dash():
    # admin123 / admin kontrolü (Sadeleştirilmiş)
    orders = Order.query.all()
    tickets = Ticket.query.all()
    return render_template_string(ADMIN_DASH_HTML, orders=orders, tickets=tickets)

# --- TASARIMLAR (HTML) ---
# (Burada sekmeli yapı, popup ile hedef sorma ve admin cevaplama kısımları yer alıyor)
LOGIN_HTML = """ ... (Önceki giriş arayüzü) ... """

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
        <h1 class="text-white font-black italic">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="bg-zinc-900 px-4 py-2 rounded-2xl border border-teal-500/20 text-white font-bold text-sm">
            <i class="fa-solid fa-coins text-yellow-500 mr-2"></i>{{ user.coins }}
        </div>
    </nav>

    <div class="flex overflow-x-auto bg-zinc-900/50 sticky top-[73px] z-40 border-b border-white/5">
        <button onclick="tab('market')" class="px-8 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max">Market</button>
        <button onclick="tab('earn')" class="px-8 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max">Coin Kas</button>
        <button onclick="tab('support')" class="px-8 py-4 text-[10px] font-bold uppercase tracking-widest min-w-max">Destek</button>
    </div>

    <main class="max-w-4xl mx-auto p-6">
        <div id="market" class="tab active grid grid-cols-1 sm:grid-cols-2 gap-4">
            {% for p in packages %}
            <div onclick="buy('{{p.n}}', {{p.c}})" class="bg-zinc-900 p-8 rounded-[2.5rem] border border-white/5 hover:border-teal-500 cursor-pointer transition">
                <h3 class="text-white font-bold">{{ p.n }}</h3>
                <p class="text-xs text-teal-500 mt-1 uppercase font-bold">{{ p.c }} Coin</p>
            </div>
            {% endfor %}
        </div>

        <div id="support" class="tab hidden space-y-4">
            <div class="bg-zinc-900 p-8 rounded-[2.5rem] border border-white/5">
                <textarea id="sup-msg" class="w-full bg-black border border-white/10 rounded-2xl p-4 text-sm h-32 mb-4" placeholder="Sorununuzu yazın..."></textarea>
                <button onclick="sendSupport()" class="w-full bg-teal-600 py-4 rounded-xl text-[10px] font-black uppercase">Mesajı Gönder</button>
            </div>
            <div class="space-y-2">
                {% for t in tickets %}
                <div class="bg-zinc-900/50 p-4 rounded-2xl border border-white/5">
                    <p class="text-xs text-white">{{ t.message }}</p>
                    {% if t.reply %}<p class="text-[10px] text-teal-500 mt-2 font-bold italic">Cevap: {{ t.reply }}</p>{% endif %}
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
        async function buy(name, cost) {
            const target = prompt("Takipçinin gönderileceği kullanıcı adını yazın:");
            if(!target) return;
            const r = await fetch('/api/order', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({package:name, cost:cost, target:target})
            });
            const d = await r.json(); alert(d.msg); if(d.status==='success') location.reload();
        }
        async function sendSupport() {
            const msg = document.getElementById('sup-msg').value;
            const r = await fetch('/api/support', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({msg:msg})
            });
            const d = await r.json(); alert(d.msg); location.reload();
        }
    </script>
</body>
</html>
"""

# ... (Admin HTML'leri buraya eklenecek) ...

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
