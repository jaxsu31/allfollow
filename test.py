import os, random, time, uuid, json
from flask import Flask, request, jsonify, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# --- 1. AYARLAR ---
app = Flask(__name__)
app.secret_key = "all_follow_v15_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v15.db"
db = SQLAlchemy(app)

# Geçici doğrulama deposu
challenge_storage = {}

# --- 2. HTML ARAYÜZÜ (DEĞİŞKEN OLARAK) ---
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>All Follow Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex items-center justify-center h-screen">
    <div class="w-96 p-8 bg-zinc-900 rounded-3xl border border-white/5 shadow-2xl">
        <h2 class="text-2xl font-black mb-6 text-center tracking-tighter">ALL FOLLOW</h2>
        
        <div class="space-y-4">
            <div id="login-fields">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm outline-none focus:border-blue-500 transition">
                <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl text-sm mt-2 outline-none focus:border-blue-500 transition">
            </div>

            <div id="verify-fields" class="hidden">
                <p class="text-sm text-blue-400 mb-2 font-bold text-center">Instagram'dan gelen 6 haneli kodu gir:</p>
                <input id="code" placeholder="000000" class="w-full bg-zinc-800 border border-blue-500 p-4 rounded-xl text-center text-2xl tracking-[1em] outline-none">
            </div>

            <button onclick="handleProcess()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase text-sm hover:bg-blue-700 transition disabled:opacity-50">Giriş Yap</button>
            <p id="msg" class="text-xs text-center text-yellow-500 font-bold mt-4"></p>
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

            if (!u || !p) { msg.innerText = "Alanları doldur!"; return; }
            btn.disabled = true;

            if (!isChallenge) {
                msg.innerText = "Instagram'a sızılıyor...";
                try {
                    const r = await fetch('/api/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({u, p})
                    });
                    const d = await r.json();

                    if (d.status === "challenge") {
                        isChallenge = true;
                        document.getElementById('login-fields').classList.add('hidden');
                        document.getElementById('verify-fields').classList.remove('hidden');
                        btn.innerText = "KODU ONAYLA";
                        msg.innerText = d.msg;
                    } else if (d.status === "success") {
                        msg.innerText = d.msg;
                        setTimeout(() => window.location.href = "/panel", 1000);
                    } else {
                        msg.innerText = d.msg;
                    }
                } catch(e) { msg.innerText = "Hata oluştu!"; }
            } else {
                // KODU ONAYLA
                msg.innerText = "Kod doğrulanıyor...";
                try {
                    const r = await fetch('/api/verify', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({u, code})
                    });
                    const d = await r.json();
                    msg.innerText = d.msg;
                    if (d.status === "success") setTimeout(() => window.location.href = "/panel", 1000);
                } catch(e) { msg.innerText = "Doğrulama hatası!"; }
            }
            btn.disabled = false;
        }
    </script>
</body>
</html>
"""

# --- 3. YOLLAR (ROUTES) ---

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    # Buraya kendi PROXY_LIST'inden birini ekle
    cl.set_proxy("http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959")
    
    try:
        cl.login(u, p)
        session['user'] = u
        return jsonify(status="success", msg="Giriş Başarılı! ✅")
    except Exception as e:
        err = str(e).lower()
        if "checkpoint" in err or "challenge" in err:
            challenge_storage[u] = {"client": cl}
            return jsonify(status="challenge", msg="Doğrulama kodu gerekli!")
        return jsonify(status="error", msg="Giriş başarısız, bilgileri kontrol et.")

@app.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.json
    u, code = data.get('u'), data.get('code')
    if u in challenge_storage:
        cl = challenge_storage[u]["client"]
        try:
            # Kod onaylama (bazı versiyonlarda login içine de gönderilebilir)
            cl.check_line_otp(u, code) 
            session['user'] = u
            return jsonify(status="success", msg="Onaylandı! ✅")
        except:
            return jsonify(status="error", msg="Kod hatalı!")
    return jsonify(status="error", msg="Oturum zaman aşımı.")

@app.route('/panel')
def panel():
    if 'user' not in session: return "Yetkisiz Giriş!"
    return f"<h1>Panel: Hoşgeldin {session['user']}</h1>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
