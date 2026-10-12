import os
import sys
import threading
from flask import Flask
import telebot
from google import genai
from deep_translator import GoogleTranslator

# 1. تشغيل خادم Flask لمنع إيقاف الخدمة في Render
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# 2. إعدادات النظام والمفاتيح
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != 'utf-8':
    sys.reconfigure(encoding='utf-8')

# جلب المفاتيح من متغيرات البيئة
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# طباعة للتأكد من وجود المفاتيح عند الإقلاع
if not BOT_TOKEN:
    print("❌ تحذير: متغير BOT_TOKEN غير موجود في Environment Variables!")
if not GEMINI_API_KEY:
    print("❌ تحذير: متغير GEMINI_API_KEY غير موجود في Environment Variables!")

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

ALLOWED_USERS = ["iyedbd"]
TARGET_THREAD_ID = None

def translate_with_gemini(text):
    if not ai_client:
        raise ValueError("GEMINI_API_KEY مفقود أو غير مضبوط في Render")

    prompt = f"""You are an expert context-aware translator.
Translate the following Arabic text into natural, accurate English.
Handle context, Arabic slang, and gaming terms naturally without literal translation.
Return ONLY the English translation without quotes or explanations.

Text:
{text}"""

    # تجربة النماذج المتاحة
    for model_name in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"فشل النموذج {model_name}: {e}")
            continue

    raise RuntimeError("فشلت جميع نماذج Gemini المتاحة.")

def translate_message(text):
    # المحاولة الأولى: Gemini
    try:
        return translate_with_gemini(text)
    except Exception as gemini_err:
        print(f"❌ عطل في Gemini: {gemini_err}")

    # المحاولة الثانية: مترجم الطوارئ
    try:
        return GoogleTranslator(source='ar', target='en').translate(text)
    except Exception as fallback_err:
        print(f"❌ عطل في المترجم البديل: {fallback_err}")
        raise fallback_err

def is_authorized(message):
    if not message.from_user or not message.from_user.username:
        return False
    return message.from_user.username.lower() in [u.lower() for u in ALLOWED_USERS]

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
            print(f"✅ تمت الترجمة بنجاح: {translated}")
    except Exception as err:
        print(f"فشلت الترجمة بالكامل: {err}")
        bot.reply_to(message, "تعذر الترجمة حالياً، حاول مجدداً بعد لحظات.")

if __name__ == "__main__":
    print("البوت يعمل الآن...")
    bot.infinity_polling(skip_pending=True)
