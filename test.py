import os, random, time, uuid, json
from flask import Flask, request, jsonify, session
# ... (Diğer importlar aynı)

# Session dosyalarının tutulacağı klasör
SESSION_FOLDER = "sessions"
if not os.path.exists(SESSION_FOLDER):
    os.makedirs(SESSION_FOLDER)

# 1. Önce kütüphaneleri içe aktar (Import)
import os, random, time, uuid, json
from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# 2. BURAYA EKLE: Uygulamayı ve Veritabanını Tanımla
app = Flask(__name__)
app.secret_key = "all_follow_v15_secret"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///all_follow_v15.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 3. ŞİMDİ ROTALARI TANIMLAYABİLİRSİN
@app.route('/api/login', methods=['POST'])
def api_login():
    # ... senin login fonksiyonun içeriği buraya gelecek ...
    return jsonify(status="success")

# 4. EN SONA DA ÇALIŞTIRMA KOMUTUNU EKLE
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=10000)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    session_file = os.path.join(SESSION_FOLDER, f"{u}.json")
    
    cl = Client()
    
    # 1. PROXY AYARI (Burayı düzelttik)
    px = random.choice(PROXY_LIST)
    cl.set_proxy(px) 
    
    # 2. LOCALE VE DİL AYARI (Proxy TR olduğu için önemli)
    cl.set_locale("tr_TR")
    cl.set_timezone_offset(3 * 3600)

    try:
        # 3. SESSION KONTROLÜ (Daha önce giriş yapılmış mı?)
        if os.path.exists(session_file):
            print(f"[*] {u} için eski oturum yükleniyor...")
            cl.load_settings(session_file)
            try:
                cl.get_timeline_feed() # Oturum hala geçerli mi kontrol et
                return jsonify(status="success", msg="Oturum Yenilendi! ✅")
            except:
                print("[!] Oturum geçersiz, yeniden login olunuyor...")
                os.remove(session_file)

        # 4. YENİ LOGIN SÜRECİ
        # Cihazı kullanıcıya özel sabitleyelim (Random ama hep aynı kalacak şekilde)
        cl.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "device": "Samsung Galaxy S9",
            "model": "SM-G960F",
            "device_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, u)), # Kullanıcıya özel sabit ID
        })

        print(f"[*] {u} için yeni giriş denemesi...")
        time.sleep(random.uniform(2, 5)) # Biraz daha uzun bekleme
        
        if cl.login(u, p):
            # Giriş başarılıysa ayarları kaydet
            cl.dump_settings(session_file)
            
            # Veritabanı işlemleri
            user = User.query.filter_by(username=u).first()
            if not user:
                user = User(username=u, password=p)
                db.session.add(user)
            db.session.commit()
            
            session['user'] = u
            return jsonify(status="success", msg="Giriş Başarılı! ✅")

    except Exception as e:
        error_text = str(e).lower()
        print("KRİTİK HATA:", error_text)
        
        if "challenge" in error_text or "checkpoint" in error_text:
            return jsonify(status="error", msg="ONAY GEREKLİ! Instagram uygulamasını aç.")
        if "bad_password" in error_text:
            return jsonify(status="error", msg="Şifre veya kullanıcı adı hatalı.")
        if "rate_limit" in error_text:
            return jsonify(status="error", msg="Çok fazla deneme! 1 saat bekleyin.")
        if "please wait a few minutes" in error_text:
            return jsonify(status="error", msg="Instagram spam algıladı, biraz bekle.")
            
        return jsonify(status="error", msg="Giriş başarısız! Proxy veya Hesap kaynaklı.")
