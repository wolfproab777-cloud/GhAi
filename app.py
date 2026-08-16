import os
import random
import string
import logging
import requests
import time
from flask import Flask, send_file, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sizning botingizning tokeni (BotFather ga xabar yuboradi)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOTFATHER_TOKEN = os.getenv("BOTFATHER_TOKEN") or TELEGRAM_BOT_TOKEN

# =======================
# ROUTELAR
# =======================

@app.route('/')
def index():
    try:
        return send_file('index.html')
    except Exception as e:
        return f"❌ Xatolik: {str(e)}"

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '').lower().strip()
        
        if not message:
            return jsonify({"response": "❌ Xabar yozing!"})
        
        response = process_message(message)
        return jsonify({"response": response})
    except Exception as e:
        logger.error(f"Chat xatosi: {e}")
        return jsonify({"response": f"❌ Xatolik: {str(e)}"})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "message": "BotYarat ishlamoqda!"})

# =======================
# ASOSIY LOGIKA
# =======================

def process_message(message):
    """Xabarni qayta ishlash"""
    
    if 'bot yarat' in message or 'bot yasash' in message:
        return """🤖 Bot yaratish uchun quyidagi formatda yozing:

`bot: NOM | USERNAME`

Masalan:
`bot: Mening Botim | mening_botim_bot`

⚠️ Username oxiri **`_bot`** bilan tugashi shart!"""
    
    if 'bot:' in message:
        try:
            parts = message.split('|')
            if len(parts) == 2:
                name = parts[0].replace('bot:', '').strip()
                username = parts[1].strip()
                
                if not username.endswith('_bot'):
                    return "❌ Username **`_bot`** bilan tugashi shart!"
                
                # BotFather orqali bot yaratish
                result = create_bot_with_botfather(name, username)
                
                if result['success']:
                    return f"""✅ **Bot muvaffaqiyatli yaratildi!**

🤖 **Nomi:** {name}
🔗 **Username:** @{username}
🔑 **API Token:**
`{result['token']}`

⚠️ **Bu tokenni hech kimga bermang!**
📌 Botni @BotFather da boshqaring."""
                else:
                    return f"❌ Xatolik: {result.get('error', 'Noma\'lum xato')}"
        except Exception as e:
            return f"❌ Xatolik: {str(e)}\n📌 Format: `bot: NOM | USERNAME`"
    
    if 'salom' in message or 'assalom' in message:
        return "👋 Salom! Bot yaratishga yordam beraman.\n\n✏️ **'bot yarat'** deb yozing!"
    
    if 'yordam' in message or 'help' in message:
        return """🤖 **BotYarat yordamchisi**

📌 **Buyruqlar:**
• `bot yarat` - yangi bot yaratish
• `bot: NOM | USERNAME` - bot yaratish
• `salom` - salomlashish
• `yordam` - bu yordam"""
    
    return "🤔 Tushunmadim.\n\n📌 **'bot yarat'** deb yozing!"

# =======================
# BOTFATHER BILAN ISHLASH
# =======================

def create_bot_with_botfather(name, username):
    """
    BotFather orqali haqiqiy bot yaratish
    """
    try:
        # 1. Username bandligini tekshirish
        if check_username_exists(username):
            return {
                "success": False,
                "error": f"@{username} band! Boshqa username tanlang."
            }
        
        # 2. BotFather ga so'rov yuborish
        # BotFather ga xabar yuborish uchun sizning botingizdan foydalanamiz
        message = f"/newbot\n{name}\n{username}"
        
        # BotFather ga xabar yuborish
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": "BotFather",
            "text": message
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            # BotFather dan javob olish uchun biroz kutish kerak
            time.sleep(3)
            
            # BotFather dan token olish
            token = get_token_from_botfather()
            
            if token:
                return {
                    "success": True,
                    "name": name,
                    "username": username,
                    "token": token
                }
            else:
                return {
                    "success": False,
                    "error": "Tokenni olishda xatolik"
                }
        else:
            return {
                "success": False,
                "error": "BotFather ga xabar yuborishda xatolik"
            }
            
    except Exception as e:
        logger.error(f"BotFather xatosi: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def check_username_exists(username):
    """
    Username bandligini tekshirish
    """
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChat"
        params = {"chat_id": f"@{username}"}
        response = requests.get(url, params=params, timeout=5)
        
        # Agar 200 qaytsa, username bor
        return response.status_code == 200
    except:
        return False

def get_token_from_botfather():
    """
    BotFather dan token olish
    """
    try:
        # BotFather dan oxirgi xabarlarni o'qish
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        params = {"offset": -1, "limit": 5}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    if 'message' in update:
                        text = update['message'].get('text', '')
                        # Token formatini qidirish
                        if ':' in text and len(text) > 30:
                            # Token ni ajratib olish
                            lines = text.split('\n')
                            for line in lines:
                                if ':' in line and len(line.strip()) > 30:
                                    return line.strip()
        return None
    except Exception as e:
        logger.error(f"Token olish xatosi: {e}")
        return None

# =======================
# ISHGA TUSHIRISH
# =======================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
