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
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
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
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
MASTER_PASSWORD = "ghpay10"

# Bot holati
bot_app = None
bot_running = False

# Ma'lumotlar bazasi
DATA_FILE = 'data.json'
PASSWORD_FILE = 'password_data.json'

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
            "codes": {}
        }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_password_data():
    try:
        with open(PASSWORD_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "current_password": MASTER_PASSWORD,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            "history": []
        }

def save_password_data(data):
    with open(PASSWORD_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_current_password():
    data = load_password_data()
    expires_at = datetime.fromisoformat(data['expires_at'])
    if datetime.now() >= expires_at:
        return rotate_password()
    return data['current_password']

def rotate_password():
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    
    password_data = load_password_data()
    password_data['history'].append({
        "password": password_data['current_password'],
        "created_at": password_data['created_at'],
        "expired_at": datetime.now().isoformat()
    })
    
    now = datetime.now()
    password_data['current_password'] = new_password
    password_data['created_at'] = now.isoformat()
    password_data['expires_at'] = (now + timedelta(hours=24)).isoformat()
    save_password_data(password_data)
    
    send_password_to_admin(new_password)
    logger.info(f"🔄 Parol yangilandi: {new_password}")
    return new_password

def check_password_expiry():
    password_data = load_password_data()
    expires_at = datetime.fromisoformat(password_data['expires_at'])
    if datetime.now() >= expires_at:
        return rotate_password()
    return password_data['current_password']

# =======================
# RECAPTCHA
# =======================

def verify_recaptcha(recaptcha_response):
    """reCAPTCHA v3 ni tekshirish"""
    try:
        if not recaptcha_response:
            return False
        
        RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
        if not RECAPTCHA_SECRET_KEY:
            return True
        
        url = "https://www.google.com/recaptcha/api/siteverify"
        data = {
            "secret": RECAPTCHA_SECRET_KEY,
            "response": recaptcha_response
        }
        
        response = requests.post(url, data=data, timeout=5)
        result = response.json()
        
        # v3 da score ni tekshirish (0.5 dan yuqori bo'lsa yaxshi)
        if result.get('success') and result.get('score', 0) >= 0.5:
            return True
        
        return False
    except Exception as e:
        logger.error(f"reCAPTCHA xatosi: {e}")
        return False

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

def send_password_to_admin(password):
    try:
        if not TELEGRAM_BOT_TOKEN or not ADMIN_USER_ID:
            logger.warning("Admin ID topilmadi")
            return {"success": False, "error": "Admin ID topilmadi"}
        
        message = f"""🔐 **Yangi parol yaratildi!**

🔑 Parol: <code>{password}</code>
📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⏳ Amal qilish: 24 soat

📌 Bu parol faqat sizga yuborildi.
Foydalanuvchilar "Parol olish" tugmasi orqali o'zlariga olishlari mumkin."""

        return send_telegram_message(ADMIN_USER_ID, message)
    except Exception as e:
        logger.error(f"Admin xatosi: {e}")
        return {"success": False, "error": str(e)}

def send_password_to_user(user_id, password):
    try:
        if not TELEGRAM_BOT_TOKEN:
            return {"success": False, "error": "Bot tokeni topilmadi"}
        
        message = f"""🔑 **Sizning parolingiz!**

🔐 Parol: <code>{password}</code>
⏳ Amal qilish: 24 soat

📌 Saytga kirish uchun ushbu paroldan foydalaning."""

        return send_telegram_message(user_id, message)
    except Exception as e:
        logger.error(f"Foydalanuvchiga yuborish xatosi: {e}")
        return {"success": False, "error": str(e)}

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
# FLASK ROUTELAR
# =======================

@app.route('/')
def index():
    try:
        check_password_expiry()
        if is_session_valid():
            return send_file('index.html')
        else:
            session.clear()
            return send_file('index.html')
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
        recaptcha = data.get('recaptcha', '')
        
        # reCAPTCHA tekshirish
        if not verify_recaptcha(recaptcha):
            return jsonify({
                "success": False,
                "error": "❌ Iltimos, 'Men robot emasman' ni tasdiqlang!"
            })
        
        current_password = get_current_password()
        
        if password == current_password:
            create_session()
            return jsonify({
                "success": True,
                "message": "✅ Kirish muvaffaqiyatli!",
                "expires_in": "24 soat"
            })
        else:
            return jsonify({
                "success": False,
                "error": "❌ Noto'g'ri parol!"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/request_password', methods=['POST'])
def request_password():
    try:
        data = request.json
        user_id = data.get('user_id', '')
        
        if not user_id:
            return jsonify({"success": False, "error": "ID kerak"})
        
        current_password = get_current_password()
        result = send_password_to_user(user_id, current_password)
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": "✅ Parol Telegram bot orqali yuborildi!"
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Parol yuborishda xatolik')
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/refresh_password', methods=['POST'])
def refresh_password():
    try:
        data = request.json
        user_id = data.get('user_id', '')
        
        if user_id != ADMIN_USER_ID:
            return jsonify({
                "success": False,
                "error": "❌ Ruxsat yo'q! Faqat admin yangilay oladi."
            })
        
        new_password = rotate_password()
        return jsonify({
            "success": True,
            "new_password": new_password,
            "message": "✅ Parol yangilandi va admin ga yuborildi!"
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

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Chiqildi"})

# =======================
# ASOSIY LOGIKA
# =======================

def process_message(message, user_id='unknown'):
    msg = message.lower().strip()
    
    if 'parol' in msg or 'password' in msg:
        current_password = get_current_password()
        result = send_password_to_user(user_id, current_password)
        if result['success']:
            return "🔑 **Parol Telegram bot orqali yuborildi!**\n\n📌 Telegramni tekshiring."
        else:
            return f"❌ Xatolik: {result.get('error', 'Noma\'lum xato')}"
    
    if msg == 'yoz' or msg == 'yozish':
        return """✍️ **Xabar yozish**

📌 Kimga xabar yozmoqchisiz?
Telegram ID sini yozing:

`id: 123456789`"""
    
    if msg.startswith('id:'):
        global target_id
        try:
            target_id = msg.replace('id:', '').strip()
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
    
    if 'salom' in msg or 'assalom' in msg:
        return "👋 Salom! GhAi yordamchisiman.\n\n📌 **Buyruqlar:**\n• `yoz` - xabar yozish\n• `parol` - parol olish\n• `bot yarat` - bot yaratish"
    
    if 'yordam' in msg or 'help' in msg:
        return """🤖 **GhAi yordamchisi**

📌 **Buyruqlar:**
• `yoz` - boshqa odamga xabar yozish
• `parol` - parol olish
• `bot yarat` - bot yaratish
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
        "👋 Salom! Men GhAi yordamchisiman!\n\n"
        "📌 **Buyruqlar:**\n"
        "• `yoz` - boshqa odamga xabar yozish\n"
        "• `parol` - parol olish\n"
        "• `bot yarat` - bot yaratish\n"
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
    check_password_expiry()
    start_telegram_bot()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
