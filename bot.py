import os
import sys
import threading
from flask import Flask
import telebot
from google import genai
from deep_translator import GoogleTranslator

# -------------------------------------------------------------
# 1. خادم ويب مصغر لإرضاء Render ومنع إغلاق الخدمة
# -------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# تشغيل الخادم في مسار منفصل
threading.Thread(target=run_flask, daemon=True).start()

# -------------------------------------------------------------
# 2. قراءة المفاتيح من Environment Variables
# -------------------------------------------------------------
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != 'utf-8':
    sys.reconfigure(encoding='utf-8')

# جلب القيم من Render مباشرة
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# اليوزرات المسموح لها بالترجمة
ALLOWED_USERS = ["iyedbd"]
TARGET_THREAD_ID = None

# -------------------------------------------------------------
# 3. دوال الترجمة
# -------------------------------------------------------------
def translate_with_gemini(text):
    prompt = f"""You are an expert context-aware translator.
Translate the following Arabic text into accurate, idiomatic English.
Handle slang, local expressions, and gaming terms naturally without literal translation.
Return ONLY the English translation without quotes, notes, or explanations.

Arabic:
{text}"""

    response = ai_client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt
    )
    return response.text.strip()

def translate_message(text):
    # المحاولة الأولى: Gemini
    try:
        return translate_with_gemini(text)
    except Exception as gemini_err:
        print(f"عطل في Gemini: {gemini_err} -> جاري استخدام المترجم البديل...")

    # المحاولة الثانية: مترجم بديل للطوارئ
    try:
        return GoogleTranslator(source='ar', target='en').translate(text)
    except Exception as fallback_err:
        print(f"فشل المترجم البديل: {fallback_err}")
        raise fallback_err

def is_authorized(message):
    if not message.from_user or not message.from_user.username:
        return False
    return message.from_user.username.lower() in [u.lower() for u in ALLOWED_USERS]

# -------------------------------------------------------------
# 4. استقبال الرسائل ومعالجتها
# -------------------------------------------------------------
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not is_authorized(message):
        return

    if TARGET_THREAD_ID is not None and message.message_thread_id != TARGET_THREAD_ID:
        return

    try:
        translated = translate_message(message.text)
        if translated:
            bot.reply_to(message, translated)
    except Exception:
        bot.reply_to(message, "تعذر الترجمة حالياً، حاول مجدداً بعد لحظات.")

# -------------------------------------------------------------
# 5. تشغيل البوت
# -------------------------------------------------------------
if __name__ == "__main__":
    print("البوت يعمل الآن مع خادم الويب ونموذج Gemini بنجاح...")
    bot.infinity_polling(skip_pending=True)
