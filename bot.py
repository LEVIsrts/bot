import os
import sys
import threading
from flask import Flask
import telebot
from google import genai
from deep_translator import GoogleTranslator

# -------------------------------------------------------------
# 1. إعداد خادم Flask لإرضاء فحص المنافذ (Web Service) في Render
# -------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive and running!"

def run_flask():
    # Render يمرر رقم المنفذ في متغير PORT تلقائياً
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# تشغيل خادم الويب في خلفية متوازية
threading.Thread(target=run_flask, daemon=True).start()

# -------------------------------------------------------------
# 2. إعداد التشفير والاتصال بالبوت والذكاء الاصطناعي
# -------------------------------------------------------------
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != 'utf-8':
    sys.reconfigure(encoding='utf-8')

BOT_TOKEN = "8936315525:AAGxsT-QEHTb6LI0W1lQC2h4W5fuJ_xs1zQ"
GEMINI_API_KEY = "AQ.Ab8RN6IxXhkwE9UpRqaswF0XGgRsJazVfTeZR4_o6Gwx3qswKw"

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# اليوزرات المسموح لها بالترجمة
ALLOWED_USERS = ["iyedbd"]
TARGET_THREAD_ID = None

def translate_with_gemini(text):
    prompt = f"""You are an expert context-aware translator.
Translate the following Arabic text into accurate, idiomatic English.
Handle slang, local expressions, and gaming terms naturally.
Return ONLY the translation without any quotes, prefaces, or notes.

Text:
{text}"""

    response = ai_client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt
    )
    return response.text.strip()

def translate_message(text):
    # المحاولة الأولى باستخدام Gemini
    try:
        return translate_with_gemini(text)
    except Exception as gemini_err:
        print(f"عطل في Gemini: {gemini_err} -> جاري استخدام المترجم البديل...")

    # في حال حدوث أي عطل في Gemini، التبديل التلقائي للمترجم الاحتياطي
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
# 3. معالجة رسائل تيليجرام
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
# 4. تشغيل البوت
# -------------------------------------------------------------
if __name__ == "__main__":
    print("البوت يعمل الآن مع خادم الويب ونموذج Gemini بنجاح...")
    bot.infinity_polling(skip_pending=True)
