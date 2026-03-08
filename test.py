import os, random, time, uuid
from flask import Flask, request, jsonify, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# --- 1. AYARLAR VE VERİTABANI ---
app = Flask(__name__)
app.secret_key = "all_follow_v15_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v15.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Geçici depolama (Kod doğrulaması için)
challenge_storage = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    coins = db.Column(db.Integer, default=10)

# --- 2. HTML ARAYÜZÜ ---
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>All Follow Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body class="bg-black text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-sm p-8 bg-zinc-900 rounded-3xl border border-white/5 shadow-2xl mx-4">
        <h2 class="text-2xl font-black mb-6 text-center tracking-tighter">ALL FOLLOW</h2>
        
        <div class="space-y-4">
            <div id="login-fields">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none focus:border-blue-500 transition">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm mt-2 outline-none focus:border-blue-500 transition">
            </div>

            <div id="verify-fields" class="hidden text-center">
                <p class="text-sm text-blue-400 mb-4 font-bold">Instagram Onay Kodu Gönderdi!</p>
                <input id="code" placeholder="000000" class="w-full bg-zinc-800 border border-blue-500 p-4 rounded-xl text-center text-2xl tracking-[0.5em] outline-none">
            </div>

            <button onclick="handleProcess()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase text-sm hover:bg-blue-700 transition">GİRİŞ YAP</button>
            <p id="msg" class="text-xs text-center text-yellow-500 font-bold mt-4 min-h-[1rem]"></p>
        </div>
    </div>

    <script>
        let isChallenge = false;

        async function handleProcess() {
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            const code = document.getElementById('code').value;
            const btn = document.getElementById('btn');
            const msg = document.getElementById('msg');

            if (!u || !p) { msg.innerText = "Lütfen bilgileri doldur!"; return; }
            
            btn.disabled = true;
            btn.innerText = "İŞLENİYOR...";

            const url = isChallenge ? '/api/verify' : '/api/login';
            const body = isChallenge ? { u, code } : { u, p };

            try {
                const r = await fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                const d = await r.json();

                msg.innerText = d.msg;

                if (d.status === "challenge") {
                    isChallenge = true;
                    document.getElementById('login-fields').classList.add('hidden');
                    document.getElementById('verify-fields').classList.remove('hidden');
                    btn.innerText = "KODU ONAYLA";
                } else if (d.status === "success") {
                    setTimeout(() => window.location.href = "/panel", 1000);
                }
            } catch(e) { 
                msg.innerText = "Bağlantı hatası oluştu!"; 
            } finally {
                btn.disabled = false;
                if(!isChallenge) btn.innerText = "GİRİŞ YAP";
            }
        }
    </script>
</body>
</html>
"""

# --- 3. API YOLLARI ---

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # Senin residential proxylerinden birini kullanıyoruz
    proxy = "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
    cl.set_proxy(proxy)
    
    try:
        # Cihaz ayarlarını sabitleyelim
        cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "device": "Samsung Galaxy S9"})
        
        print(f"[*] Giriş deneniyor: {u}")
        cl.login(u, p)
        
        # Giriş direkt başarılıysa
        session['user'] = u
        return jsonify(status="success", msg="Giriş Başarılı! ✅")

    except Exception as e:
        err = str(e).lower()
        print(f"[!] Hata Yakalandı: {err}")

        # Eğer Instagram kod istiyorsa
        if "checkpoint" in err or "challenge" in err or "two-factor" in err:
            challenge_storage[u] = {"client": cl}
            return jsonify(status="challenge", msg="Doğrulama kodu gerekli!")
        
        # Eğer "Engelledi" mesajı alıyorsak ama ID varsa (Sahte Hata)
        if cl.user_id:
            session['user'] = u
            return jsonify(status="success", msg="Giriş Başarılı! ✅")

        return jsonify(status="error", msg="Instagram girişi reddetti veya bilgiler hatalı.")

@app.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.json
    u, code = data.get('u'), data.get('code')
    
    if u in challenge_storage:
        cl = challenge_storage[u]["client"]
        try:
            # Kodu gönderiyoruz (instagrapi'nin otomatik challenge yönetimi)
            cl.login(u, "", verification_code=code) 
            session['user'] = u
            del challenge_storage[u]
            return jsonify(status="success", msg="Kod Onaylandı! Hoş geldin. ✅")
        except Exception as e:
            return jsonify(status="error", msg=f"Kod hatalı! {str(e)}")
            
    return jsonify(status="error", msg="Oturum bulunamadı, baştan dene.")

@app.route('/panel')
def panel():
    if 'user' not in session: return "Yetkisiz Giriş!"
    return f"<body style='background:#000;color:#fff;'><h1>PANELE HOŞGELDİN {session['user']}</h1><p>Bot artık hazır.</p></body>"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # Render üzerinde 10000 portuyla çalıştırıyoruz
    app.run(host="0.0.0.0", port=10000)
