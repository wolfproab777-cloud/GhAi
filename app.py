import os
import random
import string
import logging
import asyncio
import threading
import json
import hashlib
import requests
from datetime import datetime, timedelta
from flask import Flask, send_file, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
Session(app)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =======================
# KALITLAR
# =======================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "YOUR_TELEGRAM_ID")
MASTER_PASSWORD = "ghpay10"

# Bot holati
bot_app = None
bot_running = False

# Ma'lumotlar bazasi
DATA_FILE = 'data.json'

# =======================
# MA'LUMOTLAR BAZASI
# =======================

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "users": {},
            "messages": [],
            "payments": [],
            "sessions": {},
            "password_history": [],
            "codes": {}
        }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# =======================
# SESSION FUNKSIYALARI
# =======================

def is_session_valid():
    if 'password_verified' in session and session['password_verified']:
        verified_time = session.get('verified_time', datetime.now().isoformat())
        try:
            verified_datetime = datetime.fromisoformat(verified_time)
            if datetime.now() - verified_datetime < timedelta(hours=24):
                return True
        except:
            pass
    return False

def create_session():
    session['password_verified'] = True
    session['verified_time'] = datetime.now().isoformat()
    session.permanent = True

def get_session_expiry():
    if 'verified_time' in session:
        try:
            verified_time = datetime.fromisoformat(session['verified_time'])
            expiry_time = verified_time + timedelta(hours=24)
            remaining = expiry_time - datetime.now()
            if remaining.total_seconds() > 0:
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                return f"{hours} soat {minutes} daqiqa"
        except:
            pass
    return "Tugagan"

# =======================
# TELEGRAM FUNKSIYALARI
# =======================

def send_telegram_message(user_id, text):
    try:
        if not TELEGRAM_BOT_TOKEN:
            return {"success": False, "error": "Bot tokeni topilmadi"}
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return {"success": True}
        else:
            return {"success": False, "error": f"Xatolik: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_new_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_payment_link(user_id, amount):
    payment_id = f"PAY_{user_id}_{int(datetime.now().timestamp())}"
    return f"https://my.click.uz/pay?merchant_id=YOUR_MERCHANT_ID&amount={amount}&transaction_id={payment_id}"

# =======================
# FLASK ROUTELAR
# =======================

@app.route('/')
def index():
    try:
        if is_session_valid():
            return send_file('index.html')
        else:
            session.clear()
            return send_file('index.html')  # login qismi index.html ichida
    except Exception as e:
        return f"❌ Xatolik: {str(e)}"

@app.route('/api/check_session', methods=['GET'])
def check_session():
    if is_session_valid():
        return jsonify({
            "valid": True,
            "expires_in": get_session_expiry()
        })
    else:
        return jsonify({
            "valid": False,
            "message": "Session expired. Please login again."
        })

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        password = data.get('password', '')
        
        if password == MASTER_PASSWORD:
            create_session()
            
            new_password = generate_new_password()
            
            db = load_data()
            db['password_history'].append({
                "password": new_password,
                "created_at": datetime.now().isoformat(),
                "updated_by": "user_login"
            })
            save_data(db)
            
            if TELEGRAM_BOT_TOKEN and ADMIN_USER_ID:
                send_telegram_message(
                    ADMIN_USER_ID,
                    f"🔐 **Yangi parol yaratildi!**\n\n"
                    f"📌 Parol: `{new_password}`\n"
                    f"📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⏳ Amal qilish vaqti: 24 soat"
                )
            
            return jsonify({
                "success": True,
                "message": "✅ Kirish muvaffaqiyatli!",
                "new_password": new_password,
                "expires_in": "24 soat"
            })
        else:
            return jsonify({
                "success": False,
                "error": "❌ Noto'g'ri parol!"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Chiqildi"})

@app.route('/api/refresh_password', methods=['POST'])
def refresh_password():
    try:
        data = request.json
        user_id = data.get('user_id', '')
        
        new_password = generate_new_password()
        
        db = load_data()
        db['password_history'].append({
            "password": new_password,
            "created_at": datetime.now().isoformat(),
            "updated_by": user_id or "admin"
        })
        save_data(db)
        
        if TELEGRAM_BOT_TOKEN and ADMIN_USER_ID:
            send_telegram_message(
                ADMIN_USER_ID,
                f"🔄 **Parol yangilandi!**\n\n"
                f"🔑 Yangi parol: `{new_password}`\n"
                f"📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⏳ Amal qilish: 24 soat"
            )
        
        return jsonify({
            "success": True,
            "new_password": new_password,
            "message": "✅ Parol yangilandi va botga yuborildi!"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        if not is_session_valid():
            return jsonify({
                "response": "⏳ Session tugagan! Iltimos, qayta kiring.",
                "need_login": True
            })
        
        data = request.json
        message = data.get('message', '').strip()
        user_id = data.get('user_id', 'unknown')
        
        if not message:
            return jsonify({"response": "❌ Xabar yozing!"})
        
        response = process_message(message, user_id)
        return jsonify({"response": response})
    except Exception as e:
        logger.error(f"Chat xatosi: {e}")
        return jsonify({"response": f"❌ Xatolik: {str(e)}"})

@app.route('/api/send_message', methods=['POST'])
def send_message_api():
    try:
        data = request.json
        target_id = data.get('target_id')
        text = data.get('text')
        sender_id = data.get('sender_id', 'unknown')
        
        if not target_id or not text:
            return jsonify({"success": False, "error": "ID va xabar kerak"})
        
        result = send_telegram_message(target_id, text)
        
        if result['success']:
            db = load_data()
            db['messages'].append({
                "from": sender_id,
                "to": target_id,
                "text": text,
                "time": datetime.now().isoformat()
            })
            save_data(db)
            
            return jsonify({
                "success": True,
                "message": f"✅ Xabar @{target_id} ga yuborildi!"
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Xabar yuborishda xatolik')
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/get_code', methods=['POST'])
def get_code():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"success": False, "error": "ID kerak"})
        
        payment_link = create_payment_link(user_id, 15000)
        
        return jsonify({
            "success": True,
            "message": "🔑 Parol olish uchun 15 000 so'm to'lang",
            "payment_link": payment_link,
            "amount": 15000
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/payment_callback', methods=['POST'])
def payment_callback():
    try:
        data = request.json
        user_id = data.get('user_id')
        status = data.get('status')
        transaction_id = data.get('transaction_id')
        
        if status == 'success':
            code = generate_code()
            
            db = load_data()
            db['codes'][code] = {
                "user_id": user_id,
                "used": False,
                "created": datetime.now().isoformat()
            }
            db['payments'].append({
                "user_id": user_id,
                "amount": 15000,
                "transaction_id": transaction_id,
                "time": datetime.now().isoformat(),
                "status": "success"
            })
            save_data(db)
            
            send_telegram_message(user_id, f"🔑 Sizning parolingiz: {code}")
            
            return jsonify({
                "success": True,
                "code": code,
                "message": "✅ To'lov qabul qilindi! Parolingiz yuborildi."
            })
        else:
            return jsonify({
                "success": False,
                "message": "❌ To'lov bekor qilindi"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/get_profile', methods=['POST'])
def get_profile():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"success": False, "error": "ID kerak"})
        
        db = load_data()
        user = db['users'].get(user_id, {})
        
        return jsonify({
            "success": True,
            "profile": {
                "id": user_id,
                "name": user.get('name', 'Noma\'lum'),
                "phone": user.get('phone', 'Noma\'lum'),
                "balance": user.get('balance', 0),
                "payments": [p for p in db['payments'] if p['user_id'] == user_id]
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/verify_token', methods=['POST'])
def verify_token():
    try:
        data = request.json
        token = data.get('token', '').strip()
        
        if not token or ':' not in token:
            return jsonify({"success": False, "error": "Noto'g'ri token formati"})
        
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_info = data.get('result', {})
                return jsonify({
                    "success": True,
                    "name": bot_info.get('first_name', 'Noma\'lum'),
                    "username": bot_info.get('username', 'Noma\'lum')
                })
        
        return jsonify({"success": False, "error": "Token noto'g'ri yoki bot faol emas!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# =======================
# ASOSIY LOGIKA
# =======================

def process_message(message, user_id='unknown'):
    msg = message.lower().strip()
    
    # Yozish
    if msg == 'yoz' or msg == 'yozish':
        return """✍️ **Xabar yozish**

📌 Kimga xabar yozmoqchisiz?
Telegram ID sini yozing:

`id: 123456789`

Yoki username:
`@username`"""
    
    if msg.startswith('id:') or msg.startswith('@'):
        global target_id
        try:
            target_id = msg.replace('id:', '').replace('@', '').strip()
            return f"""📝 **{target_id} ga xabar yozish**

✏️ Xabar matnini yozing:

`xabar: Sizning matningiz`"""
        except:
            return "❌ Noto'g'ri format!"
    
    if msg.startswith('xabar:'):
        try:
            text = message.replace('xabar:', '').strip()
            if target_id:
                result = send_telegram_message(target_id, text)
                if result['success']:
                    return f"✅ **Xabar yuborildi!**\n\n📤 Kimga: {target_id}\n📝 Matn: {text}"
                else:
                    return f"❌ Xatolik: {result.get('error')}"
            else:
                return "❌ Avval ID ni tanlang! `id: 123456789`"
        except:
            return "❌ Xatolik!"
    
    # Parol olish
    if 'parol olish' in msg or 'kalit olish' in msg:
        return """🔑 **Parol olish**

💰 Narxi: <b>15 000 so'm</b>

📌 To'lov qilish uchun:
1. Quyidagi tugmani bosing
2. To'lovni amalga oshiring
3. Parolingizni oling

<a href="/api/get_code">💳 To'lov qilish</a>"""
    
    # Bot yaratish
    if 'bot yarat' in msg or 'bot yasash' in msg:
        return """🤖 Bot yaratish uchun:

1️⃣ <b>@BotFather</b> ni oching
2️⃣ <code>/newbot</code> buyrug'ini yuboring
3️⃣ Bot uchun NOM kiriting
4️⃣ Bot uchun USERNAME kiriting (oxiri <code>_bot</code> bilan)
5️⃣ API TOKEN ni shu yerga yozing:

<code>token: SIZNING_TOKENINGIZ</code>"""
    
    if msg.startswith('token:'):
        try:
            token = message.replace('token:', '').strip()
            if ':' in token and len(token) > 30:
                return f"""✅ **Token saqlandi!**

🔑 <code>{token}</code>

🤖 Botingiz tayyor! 🎉"""
            else:
                return "❌ Noto'g'ri token formati!"
        except:
            return "❌ Xatolik!"
    
    # Profil
    if 'profil' in msg or 'profile' in msg:
        db = load_data()
        user = db['users'].get(user_id, {})
        return f"""👤 **Sizning profilingiz**

🆔 ID: {user_id}
📛 Ism: {user.get('name', 'Noma\'lum')}
📱 Telefon: {user.get('phone', 'Noma\'lum')}
💰 Balans: {user.get('balance', 0)} so'm
📨 Xabarlar: {len(db['messages'])}"""
    
    # Salom
    if 'salom' in msg or 'assalom' in msg:
        return "👋 Salom! Bot yaratish va xabar yuborishga yordam beraman.\n\n📌 **Buyruqlar:**\n• `yoz` - xabar yozish\n• `parol olish` - kalit olish\n• `bot yarat` - bot yaratish\n• `profil` - profilingiz"
    
    # Yordam
    if 'yordam' in msg or 'help' in msg:
        return """🤖 **BotYarat yordamchisi**

📌 **Buyruqlar:**
• `yoz` - boshqa odamga xabar yozish
• `parol olish` - kalit olish (15 000 so'm)
• `bot yarat` - bot yaratish
• `profil` - profilingiz
• `salom` - salomlashish
• `yordam` - bu yordam

⚡ Gemini usulida ishlaydi!"""
    
    return "🤔 Tushunmadim.\n\n📌 **'yordam'** deb yozing."

# =======================
# TELEGRAM BOT HANDLERLARI
# =======================

async def telegram_start(update: Update, context):
    user_id = str(update.message.from_user.id)
    
    db = load_data()
    if user_id not in db['users']:
        db['users'][user_id] = {
            "name": update.message.from_user.first_name,
            "username": update.message.from_user.username,
            "phone": None,
            "balance": 0
        }
        save_data(db)
    
    await update.message.reply_text(
        "👋 Salom! Men BotYarat yordamchisiman!\n\n"
        "📌 **Buyruqlar:**\n"
        "• `yoz` - boshqa odamga xabar yozish\n"
        "• `parol olish` - kalit olish (15 000 so'm)\n"
        "• `bot yarat` - bot yaratish\n"
        "• `profil` - profilingiz\n"
        "• `yordam` - yordam",
        parse_mode='HTML'
    )

async def telegram_handle_message(update: Update, context):
    user_id = str(update.message.from_user.id)
    user_message = update.message.text
    
    logger.info(f"Telegram xabar: {user_id} -> {user_message}")
    
    response = process_message(user_message, user_id)
    await update.message.reply_text(response, parse_mode='HTML')

# =======================
# BOTNI ISHGA TUSHIRISH
# =======================

def start_telegram_bot():
    global bot_app, bot_running
    
    if bot_running:
        return
    
    try:
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN topilmadi!")
            return
        
        bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        bot_app.add_handler(CommandHandler("start", telegram_start))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_handle_message))
        
        def run_bot():
            asyncio.set_event_loop(asyncio.new_event_loop())
            bot_app.run_polling()
        
        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()
        
        bot_running = True
        logger.info("✅ Telegram bot ishga tushdi!")
        
    except Exception as e:
        logger.error(f"❌ Bot xatosi: {e}")

# =======================
# ISHGA TUSHIRISH
# =======================

if __name__ == '__main__':
    start_telegram_bot()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
