import os
import sys
import threading
from flask import Flask
import telebot
from openai import OpenAI
from deep_translator import GoogleTranslator

# -------------------------------------------------------------
# 1. خادم Flask لإرضاء فحص المنافذ على Render
# -------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# -------------------------------------------------------------
# 2. إعداد الترميز والمتغيرات
# -------------------------------------------------------------
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != 'utf-8':
    sys.reconfigure(encoding='utf-8')

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8936315525:AAGxsT-QEHTb6LI0W1lQC2h4W5fuJ_xs1zQ").strip()
CRATE_API_KEY = os.environ.get("CRATE_API_KEY", "cc_boyfYE1gwLJ8GMdWfxvd7cX1mbfqNRZ18b2J87rvTcvcsZ6U").strip()

bot = telebot.TeleBot(BOT_TOKEN)

# عميل CrateCraft
crate_client = OpenAI(
    api_key=CRATE_API_KEY,
    base_url="https://api.cratecraft.com/v1"
)

ALLOWED_USERS = ["iyedbd"]
TARGET_THREAD_ID = None

# -------------------------------------------------------------
# 3. دوال الترجمة
# -------------------------------------------------------------
def translate_with_cratecraft(text):
    response = crate_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert context-aware translator. "
                    "Translate the following Arabic text into accurate, natural English. "
                    "Correctly handle gaming slang, idioms, and context. "
                    "Return ONLY the translation without quotes, notes, or introductions."
                )
            },
            {"role": "user", "content": text}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def translate_message(text):
    # 1. المحاولة الأساسية عبر CrateCraft
    try:
        return translate_with_cratecraft(text)
    except Exception as crate_err:
        print(f"❌ عطل في CrateCraft: {crate_err} -> الانتقال للبديل...")

    # 2. المحاولة الاحتياطية (Google Translate)
    try:
        return GoogleTranslator(source='ar', target='en').translate(text)
    except Exception as fallback_err:
        print(f"❌ عطل في المترجم البديل: {fallback_err}")
        raise fallback_err

def is_authorized(message):
    if not message.from_user or not message.from_user.username:
        return False
    return message.from_user.username.lower() in [u.lower() for u in ALLOWED_USERS]

# -------------------------------------------------------------
# 4. معالجة الرسائل
# -------------------------------------------------------------
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    sender = message.from_user.username if message.from_user else None
    print(f"رسالة من: @{sender} | المحتوى: {message.text}")

    if not is_authorized(message):
        return

    if TARGET_THREAD_ID is not None and message.message_thread_id != TARGET_THREAD_ID:
        return

    try:
        translated = translate_message(message.text)
        if translated:
            bot.reply_to(message, translated)
            print(f"✅ تم الرد بالترجمة: {translated}")
    except Exception:
        bot.reply_to(message, "تعذر الترجمة حالياً، حاول مجدداً بعد لحظات.")

# -------------------------------------------------------------
# 5. تشغيل البوت
# -------------------------------------------------------------
if __name__ == "__main__":
    print("البوت يعمل الآن بنظام CrateCraft...")
    bot.infinity_polling(skip_pending=True)
