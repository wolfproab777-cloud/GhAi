import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token
TOKEN = os.getenv("8290288100:AAHfb8lnFyMBXlv8mDrBoH-XPvNa-mH9LLE")

# =======================
# HANDLERLAR
# =======================

async def start(update: Update, context):
    """/start buyrug'i"""
    await update.message.reply_text(
        "👋 Salom! Men BotYarat yordamchisiman!\n\n"
        "📌 Bot yaratish uchun **'bot yarat'** deb yozing.\n"
        "📌 Yordam uchun **'yordam'** deb yozing."
    )

async def handle_message(update: Update, context):
    """Oddiy xabarlarni qayta ishlash"""
    user_message = update.message.text
    username = update.message.from_user.username or "Noma'lum"
    
    logger.info(f"Xabar: {username} -> {user_message}")
    
    # AI javob
    response = process_message(user_message)
    await update.message.reply_text(response)

def process_message(message):
    """Xabarni qayta ishlash"""
    msg = message.lower().strip()
    
    if 'bot yarat' in msg or 'bot yasash' in msg:
        return """🤖 Bot yaratish uchun quyidagi ma'lumotlarni bering:

📝 **Bot nomi:** (masalan: Mening Botim)
🔗 **Username:** (masalan: mening_botim_bot)

📌 Quyidagi formatda yozing:
`bot: NOM | USERNAME`

Masalan:
`bot: Mening Botim | mening_botim_bot`"""
    
    if 'bot:' in msg:
        try:
            parts = message.split('|')
            if len(parts) == 2:
                name = parts[0].replace('bot:', '').strip()
                username = parts[1].strip()
                
                if not username.endswith('_bot'):
                    return "❌ Username **`_bot`** bilan tugashi shart!"
                
                # Haqiqiy bot yaratish (simulyatsiya)
                import random, string
                token = f"{random.randint(1000000000, 9999999999)}:{''.join(random.choices(string.ascii_letters + string.digits, k=35))}"
                
                return f"""✅ **Bot muvaffaqiyatli yaratildi!**

🤖 **Nomi:** {name}
🔗 **Username:** @{username}
🔑 **API Token:**
`{token}`

⚠️ **Bu tokenni hech kimga bermang!**"""
        except:
            return "❌ Xatolik!\n\n📌 Format: `bot: NOM | USERNAME`"
    
    if 'salom' in msg or 'assalom' in msg:
        return "👋 Salom! Bot yaratishga yordam beraman."
    
    if 'yordam' in msg or 'help' in msg:
        return """🤖 **Buyruqlar:**
• `bot yarat` - yangi bot yaratish
• `bot: NOM | USERNAME` - bot yaratish
• `salom` - salomlashish
• `yordam` - yordam"""
    
    return "🤔 Tushunmadim.\n\n📌 **'bot yarat'** deb yozing."

# =======================
# BOTNI ISHGA TUSHIRISH
# =======================

def main():
    """Botni ishga tushirish"""
    if not TOKEN:
        logger.error("❌ BOT_TOKEN topilmadi! .env faylini tekshiring.")
        return
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
