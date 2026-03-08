import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v33_super_proxy"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v33.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- PROXY LİSTESİ (OTOMATİK FORMATLANDI) ---
PROXIES = [
    f"http://pcUjiruWbB-res-tr-sid-{sid}:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
    for sid in [
        "48971455", "81726754", "54431773", "68595711", "81522546", "23737559", "76348745", 
        "23681821", "89312867", "72359257", "53933998", "12843496", "68243536", "58484294", 
        "79874699", "57632523", "57946362", "96729214", "85934821", "51651336", "27645484", 
        "26191677", "15788845", "72234459", "53964751", "35412839", "56238493", "81621991", 
        "67551827", "51465178", "31833218", "23911994", "98622267", "19172716", "99669268", 
        "35923718", "52533156", "88154169", "18425644", "17617248", "34721996", "65168661", 
        "84921573", "95165423", "44441722", "76622896", "68861553", "78558345", "22453482", "17582117"
    ]
]

# --- MODELLER ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=800)
    device_data = db.Column(db.Text)

# --- GİRİŞ MANTIĞI ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # Rastgele Proxy Seçimi
    current_proxy = random.choice(PROXIES)
    cl.set_proxy(current_proxy)
    
    # Cihaz Ayarı (TECNO KH7n)
    cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "device": "TECNO KH7n", "cpu": "mt6765"})
    cl.set_locale("tr_TR")
    cl.set_country("TR")

    try:
        print(f"DEBUG: {u} için {current_proxy} üzerinden giriş deneniyor...")
        cl.login(u, p)
        
        user = User.query.filter_by(username=u).first()
        if not user:
            user = User(username=u, password=p, device_data=json.dumps(cl.get_settings()))
            db.session.add(user)
        
        session['user'] = u
        db.session.commit()
        return jsonify(status="success")

    except Exception as e:
        err = str(e).lower()
        print(f"HATA: {err}")
        if "challenge" in err or "checkpoint" in err:
            return jsonify(status="error", msg="Onay Gerekli! Uygulamayı aç ve 'BENDİM' de.")
        if "wait a few minutes" in err:
            return jsonify(status="error", msg="Instagram bu proxy'yi yavaşlattı. Tekrar 'Giriş Yap'a basın, sistem yeni proxy seçecek.")
        return jsonify(status="error", msg="Giriş başarısız. Şifreni kontrol et.")

@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    user = User.query.filter_by(username=session['user']).first()
    return f"Sisteme Hoş Geldin {user.username}! <br> Coin: {user.coins} <br> <a href='/logout'>Çıkış Yap</a>"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- BASİT GİRİŞ EKRANI ---
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>Giriş</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="p-10 bg-zinc-900 rounded-[2rem] border border-white/5 w-80">
        <h2 class="text-center font-bold mb-6">ALLFOLLOW</h2>
        <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black p-4 rounded-xl mb-3 text-sm border border-white/10">
        <input id="p" type="password" placeholder="Şifre" class="w-full bg-black p-4 rounded-xl mb-6 text-sm border border-white/10">
        <button onclick="login()" id="btn" class="w-full bg-teal-600 py-4 rounded-xl font-bold text-xs uppercase">Giriş Yap</button>
        <p id="msg" class="text-[10px] text-yellow-500 mt-4 text-center"></p>
    </div>
    <script>
    async function login() {
        const u = document.getElementById('u').value, p = document.getElementById('p').value;
        const btn = document.getElementById('btn');
        btn.disabled = true; btn.innerText = "BAĞLANILIYOR...";
        const r = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({u, p}) });
        const d = await r.json();
        if(d.status==='success') window.location.href='/panel';
        else { document.getElementById('msg').innerText = d.msg; btn.disabled = false; btn.innerText = "Giriş Yap"; }
    }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
