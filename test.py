import os, random, time, uuid
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v16_pro_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v16.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- VERİTABANI MODELLERİ ---
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
    status = db.Column(db.String(50), default="Beklemede") # Beklemede, Tamamlandı
    timestamp = db.Column(db.DateTime, default=db.func.now())

# --- SABİTLER ---
OFFICIAL_ACC = "allfollow_resmi"
PACKAGES = [
    {"name": "100 Takipçi", "coins": 800},
    {"name": "200 Takipçi", "coins": 1600},
    {"name": "300 Takipçi", "coins": 2400},
    {"name": "400 Takipçi", "coins": 3200},
    {"name": "500 Takipçi", "coins": 4000},
    {"name": "1000 Takipçi", "coins": 8000},
    {"name": "5000 Takipçi", "coins": 40000},
]

# --- YARDIMCI FONKSİYONLAR ---
def anti_ban_delay():
    time.sleep(random.uniform(15, 45)) # Takip arası güvenli bekleme

# --- ROTALAR ---

@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    # ... (Buradaki instagrapi login kodu önceki mesajla aynı kalacak) ...
    # Giriş başarılıysa:
    user = User.query.filter_by(username=u).first()
    if not user:
        user = User(username=u, password=p, ref_code=str(uuid.uuid4())[:8])
        db.session.add(user)
        db.session.commit()
    session['user'] = u
    return jsonify(status="success", msg="Giriş Başarılı!")

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    user = User.query.filter_by(username=session['user']).first()
    
    # Zorunlu Takip Kontrolü (Simülasyon)
    if not user.is_following_official:
        return render_template_string(MUST_FOLLOW_HTML, user=user)
    
    return render_template_string(PANEL_HTML, user=user, packages=PACKAGES)

@app.route('/api/follow_official', methods=['POST'])
def follow_official():
    # Burada bot üzerinden allfollow_resmi takip edilir
    user = User.query.filter_by(username=session['user']).first()
    user.is_following_official = True
    db.session.commit()
    return jsonify(status="success")

@app.route('/api/order', methods=['POST'])
def place_order():
    data = request.json
    user = User.query.filter_by(username=session['user']).first()
    pkg = next((p for p in PACKAGES if p['name'] == data['package']), None)
    
    if user.coins >= pkg['coins']:
        user.coins -= pkg['coins']
        new_order = Order(username=user.username, package_name=pkg['name'], cost=pkg['coins'])
        db.session.add(new_order)
        db.session.commit()
        return jsonify(status="success", msg="Sipariş Alındı! 24-48 saat içinde tamamlanacaktır.")
    return jsonify(status="error", msg="Yetersiz Coin!")

# --- ADMİN PANEL ---
@app.route('/admin')
def admin_login_page():
    return '''<form action="/admin/dashboard" method="post">
              User: <input name="u"> Pass: <input name="p" type="password"> <button>Giriş</button></form>'''

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if request.method == 'POST':
        if request.form['u'] != 'admin123' or request.form['p'] != 'admin':
            return "Yetkisiz!"
        session['admin'] = True
    
    if not session.get('admin'): return redirect('/admin')
    
    orders = Order.query.order_by(Order.timestamp.desc()).all()
    return render_template_string(ADMIN_HTML, orders=orders)

# --- HTML ŞABLONLARI (TASARIM) ---

PANEL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <title>All Follow Pro</title>
</head>
<body class="bg-[#050505] text-zinc-400 font-sans">
    <nav class="border-b border-white/5 p-6 flex justify-between items-center sticky top-0 bg-black/80 backdrop-blur-lg z-50">
        <h1 class="text-white font-black tracking-tighter text-2xl italic">ALLFOLLOW<span class="text-teal-500">.</span></h1>
        <div class="flex gap-4 items-center">
            <div class="bg-zinc-900 border border-teal-500/20 px-4 py-2 rounded-2xl flex items-center gap-2">
                <i class="fa-solid fa-coins text-yellow-500 animate-pulse"></i>
                <span class="text-white font-bold">{{ user.coins }}</span>
            </div>
            <button class="bg-white text-black text-[10px] font-black px-4 py-2 rounded-lg uppercase tracking-widest hover:bg-teal-500 hover:text-white transition">Hesap Ekle +</button>
        </div>
    </nav>

    <main class="max-w-6xl mx-auto p-6 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div class="md:col-span-2 space-y-6">
            <h3 class="text-white font-bold flex items-center gap-2"><i class="fa-solid fa-shop text-teal-500"></i> Market</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {% for pkg in packages %}
                <div onclick="order('{{ pkg.name }}')" class="bg-zinc-900/50 border border-white/5 p-6 rounded-[2rem] hover:border-teal-500 transition-all cursor-pointer group">
                    <h4 class="text-white font-bold group-hover:text-teal-500 transition">{{ pkg.name }}</h4>
                    <p class="text-[10px] uppercase tracking-widest mt-1">Fiyat: {{ pkg.coins }} Coin</p>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="space-y-6">
            <div class="bg-gradient-to-br from-zinc-900 to-black border border-white/10 p-8 rounded-[2.5rem]">
                <h4 class="text-white font-bold mb-4">Referans Kodu</h4>
                <div class="bg-black/40 p-3 rounded-xl border border-dashed border-teal-500/30 text-center select-all">
                    <span class="text-teal-500 font-mono">{{ user.ref_code }}</span>
                </div>
                <p class="text-[10px] mt-4 leading-relaxed">Arkadaşlarını davet et, her başarılı girişte 200 coin kazan!</p>
            </div>
            
            <div class="bg-zinc-900/50 border border-white/5 p-8 rounded-[2.5rem]">
                <h4 class="text-white font-bold mb-4 italic">Anti-Ban Koruması</h4>
                <div class="flex items-center gap-2 text-emerald-500 text-[10px] font-bold">
                    <div class="w-2 h-2 bg-emerald-500 rounded-full animate-ping"></div>
                    SİSTEM AKTİF
                </div>
                <p class="text-[10px] mt-2">Bot, Instagram radarına takılmamak için rastgele aralıklarla işlem yapmaktadır.</p>
            </div>
        </div>
    </main>

    <script>
        async function order(pkgName) {
            if(!confirm(pkgName + " paketini almak istediğine emin misin?")) return;
            const r = await fetch('/api/order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({package: pkgName})
            });
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
    <div class="text-center p-10 bg-zinc-900 rounded-[3rem] border border-teal-500/30">
        <h2 class="text-3xl font-black mb-4">DUR YOLCU! 🛑</h2>
        <p class="text-zinc-400 text-sm mb-8">Panele erişmek için resmi hesabımızı takip etmelisin.</p>
        <a href="https://instagram.com/allfollow_resmi" target="_blank" onclick="followed()" class="bg-teal-600 px-8 py-4 rounded-2xl font-black uppercase tracking-widest text-xs hover:bg-teal-400 transition">TAKİP ET VE GİRİŞ YAP</a>
    </div>
    <script>
        async function followed() {
            setTimeout(async () => {
                await fetch('/api/follow_official', {method:'POST'});
                location.reload();
            }, 5000);
        }
    </script>
</body>
"""

ADMIN_HTML = """
<body style="background:#111; color:#fff; font-family:sans-serif; padding:50px;">
    <h2>Admin Panel - Gelen Siparişler</h2>
    <table border="1" style="width:100%; border-collapse:collapse;">
        <tr style="background:#222;"><th>Kullanıcı</th><th>Paket</th><th>Coin</th><th>Tarih</th><th>Durum</th></tr>
        {% for o in orders %}
        <tr>
            <td>{{ o.username }}</td><td>{{ o.package_name }}</td><td>{{ o.cost }}</td><td>{{ o.timestamp }}</td>
            <td style="color:orange;">{{ o.status }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
