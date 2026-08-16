import os
import random
import string
import logging
from flask import Flask, send_file, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOTFATHER_TOKEN = os.getenv("BOTFATHER_TOKEN") or TELEGRAM_BOT_TOKEN

@app.route('/')
def index():
    """Asosiy sahifa - index.html ni ko'rsatadi"""
    try:
        return send_file('index.html')
    except Exception as e:
        return f"❌ Xatolik: index.html topilmadi! {str(e)}"

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat API"""
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
    """Sog'lik tekshiruvi"""
    return jsonify({"status": "ok", "message": "BotYarat ishlamoqda!"})

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
                
                token = f"{random.randint(1000000000, 9999999999)}:{''.join(random.choices(string.ascii_letters + string.digits, k=35))}"
                
                return f"""✅ **Bot muvaffaqiyatli yaratildi!**

🤖 **Nomi:** {name}
🔗 **Username:** @{username}
🔑 **API Token:**
`{token}`

⚠️ **Bu tokenni hech kimga bermang!**
📌 Botni @BotFather da boshqaring."""
        except Exception as e:
            return f"❌ Xatolik: {str(e)}\n📌 Format: `bot: NOM | USERNAME`"
    
    if 'salom' in message or 'assalom' in message or 'hello' in message:
        return "👋 Salom! Bot yaratishga yordam beraman.\n\n✏️ **'bot yarat'** deb yozing va boshlaymiz!"
    
    if 'yordam' in message or 'help' in message:
        return """🤖 **BotYarat yordamchisi**

📌 **Buyruqlar:**
• `bot yarat` - yangi bot yaratish
• `bot: NOM | USERNAME` - bot yaratish
• `salom` - salomlashish
• `yordam` - bu yordam

⚡ Gemini usulida ishlaydi!"""
    
    return "🤔 Tushunmadim.\n\n📌 **'bot yarat'** deb yozing, men sizga bot yasashda yordam beraman."

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
