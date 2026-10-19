"""
handlers.py - جميع معالجات الأوامر والأزرار التفاعلية
"""
import logging
import os
import tempfile
from datetime import datetime

from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database as db
from config import ADMIN_IDS, ALL_ROOMS, DAY_MAP, GEMINI_API_KEY, TOPIC_ID, REMINDER_MINUTES_BEFORE
from keyboards import (
    admin_main_menu,
    sessions_keyboard,
    edit_options_keyboard,
    room_type_keyboard,
    cc_rooms_keyboard,
    normal_rooms_keyboard,
    amphi_rooms_keyboard,
    confirm_keyboard,
    day_schedule_keyboard,
    week_overview_keyboard,
    next_session_keyboard,
    language_select_keyboard,
    settings_menu_keyboard,
    translate_settings_keyboard,
    schedule_topic_settings_keyboard,
    gemini_settings_keyboard,
)
from schedule_formatter import (
    format_day_schedule,
    format_week_overview,
    format_next_card,
    get_today_name,
    get_tomorrow_name,
    get_current_datetime,
    to_day_en,
    to_day_ar,
    STUDY_DAYS,
)
from pdf_parser import parse_schedule_pdf

logger = logging.getLogger(__name__)


def translate_with_gemini(text: str, api_key: str, target_lang: str = "en") -> str | None:
    """ترجمة احترافية ودقيقة بواسطة Google Gemini AI (gemini-3.6-flash)."""
    if not api_key or not text.strip():
        return None

    import urllib.request
    import urllib.error
    import json

    if target_lang == "ar":
        instruction = (
            "You are a professional instant translator from English to Arabic. "
            "Translate the given English text accurately into clear, modern, natural Arabic. "
            "Preserve emojis, acronyms, and technical terms. "
            "Output ONLY the raw Arabic translation. "
            "Do not include quotes, notes, pronunciation, or explanations."
        )
    else:
        instruction = (
            "You are a professional instant translator from Arabic to English. "
            "Translate the given Arabic text accurately into clean, natural modern English. "
            "Preserve emojis, acronyms, and technical terms. "
            "Output ONLY the raw English translation. "
            "Do not include quotes, notes, pronunciation, or explanations."
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": text.strip()}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {
                    "text": instruction
                }
            ]
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1000
        }
    }

    models = [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-flash-latest",
    ]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        res = parts[0].get("text", "").strip()
                        if res:
                            logger.info(f"✨ تمت الترجمة بنجاح عبر Gemini ({model}) إلى {target_lang}")
                            return res
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            logger.debug(f"⚠️ [Gemini {model}] HTTP {e.code}: {err_msg[:120]}")
            continue
        except Exception as e:
            logger.debug(f"⚠️ [Gemini {model}] خطأ: {e}")
            continue

    return None


def translate_text(text: str, target_mode: str = "auto") -> tuple[str, str]:
    """
    ترجمة ذكية تدعم الخيارات (عربي -> إنجليزي | إنجليزي -> عربي | تلقائي ثنائي).
    ترجع: (النص_المترجم, كود_اللغة 'en' أو 'ar')
    """
    if not text or not text.strip():
        return "", ""

    raw_text = text.strip()
    import re

    has_ar = bool(re.search(r"[\u0600-\u06FF]", raw_text))
    has_en = bool(re.search(r"[a-zA-Z]", raw_text))

    if target_mode == "en":
        target = "en"
    elif target_mode == "ar":
        target = "ar"
    else:  # auto
        if has_ar:
            target = "en"
        elif has_en:
            target = "ar"
        else:
            return "", ""

    # 1. المحرك الأول الذكي: Google Gemini AI
    gemini_key = db.get_setting("gemini_api_key") or GEMINI_API_KEY
    if gemini_key:
        try:
            res_gemini = translate_with_gemini(raw_text, gemini_key, target_lang=target)
            if res_gemini and res_gemini.strip() and res_gemini.strip().lower() != raw_text.strip().lower():
                return res_gemini.strip(), target
        except Exception as e:
            logger.warning(f"⚠️ تعذر الترجمة بـ Gemini، جاري التبديل للمحرك الاحتياطي: {e}")

    # 2. المحرك الاحتياطي الفوري: Google Translate GTX
    import urllib.request
    import urllib.parse
    import json

    encoded = urllib.parse.quote(raw_text)

    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list) and isinstance(data[0], list):
                res = "".join(item[0] for item in data[0] if isinstance(item, list) and item and item[0])
                if res and res.strip() and res.strip().lower() != raw_text.strip().lower():
                    return res.strip(), target
    except Exception as e:
        logger.debug(f"⚠️ [Google GTX Translate] فشل: {e}")

    # 3. المحرك الثالث: Google Chrome Extension API
    try:
        url = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl={target}&q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                parts = [item[0] for item in data if isinstance(item, list) and item and item[0]]
                if parts:
                    res = " ".join(parts).strip()
                    if res and res.lower() != raw_text.lower():
                        return res, target
    except Exception as e:
        logger.debug(f"⚠️ [Google Chrome Extension API] فشل: {e}")

    return raw_text, target


def translate_ar_to_en(text: str) -> str:
    """دالة التوافقية السابقة للترجمة إلى الإنجليزية."""
    res, _ = translate_text(text, target_mode="en")
    return res


# ══════════════════════════════════════════════════════════════
#  التحقق من صلاحيات المشرف
# ══════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    """تحقق إذا كان المستخدم مشرفاً (في الـ config أو قاعدة البيانات)."""
    return user_id in ADMIN_IDS or user_id in db.get_db_admins()


async def _check_admin(update: Update) -> bool:
    """أرسل رسالة خطأ إذا لم يكن المستخدم مشرفاً وأرجع False."""
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text(
            "⛔ عذراً، هذا الأمر مخصص للمشرفين فقط."
        )
        return False
    return True


# ══════════════════════════════════════════════════════════════
#  الأوامر الأساسية
# ══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name or user.username or "مستخدم"

    # تسجيل العضو تلقائياً
    db.upsert_member(user.id, user.username, user.full_name or name)
    user_lang = db.get_user_lang(user.id)

    if user_lang == "en":
        if is_admin(user.id):
            await update.message.reply_text(
                f"👋 Welcome <b>{name}</b>!\n\n"
                "🤖 <b>Study Schedule & Smart Assistant Bot</b>\n\n"
                "📌 <b>Schedule Commands:</b>\n"
                "• /schedule or /today — Interactive Today's Schedule\n"
                "• /tomorrow — Tomorrow's Schedule\n"
                "• /next — Next & Ongoing Session\n"
                "• /week or /fullschedule — Full Weekly Schedule\n"
                "• /day <i>[day]</i> — Custom Day Schedule (e.g. <code>/day Sunday</code>)\n"
                "• /lang — Switch Interface Language (English / عربي)\n\n"
                "⚙️ Admin Panel: /panel\n"
                "📄 You can also upload a PDF file to update the schedule automatically.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                f"👋 Welcome <b>{name}</b>!\n\n"
                "📅 <b>Study Schedule Tracker Bot</b>\n\n"
                "📌 <b>Schedule Commands:</b>\n"
                "• /schedule or /today — Interactive Today's Schedule\n"
                "• /tomorrow — Tomorrow's Schedule\n"
                "• /next — Next & Ongoing Session\n"
                "• /week — Full Weekly Schedule\n"
                "• /day <i>[day]</i> — Custom Day Schedule (e.g. <code>/day Sunday</code>)\n"
                "• /lang — Switch Interface Language (English / عربي)\n\n"
                "⏰ Automatic reminders are sent 15 minutes before every class in the group.",
                parse_mode=ParseMode.HTML,
            )
        return

    if is_admin(user.id):
        await update.message.reply_text(
            f"👋 أهلاً بك يا <b>{name}</b>!\n\n"
            "🤖 <b>بوت الجدول الدراسي والتحكم الذكي</b>\n\n"
            "📌 <b>أوامر استعراض الجداول:</b>\n"
            "• /schedule أو /today — جدول اليوم التفاعلي\n"
            "• /tomorrow — جدول الغد\n"
            "• /next — الحصة القادمة والجارية الآن\n"
            "• /week أو /fullschedule — الجدول الأسبوعي الكامل\n"
            "• /day <i>[اليوم]</i> — جدول يوم مخصص (مثال: <code>/day الأحد</code>)\n"
            "• /lang — تغيير لغة الواجهة (عربي / English)\n\n"
            "⚙️ لوحة المشرف: /panel\n"
            "📄 يمكنك أيضاً إرسال ملف PDF لتحديث الجدول تلقائياً.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"👋 أهلاً بك يا <b>{name}</b>!\n\n"
            "📅 <b>بوت متابعة الجدول الدراسي</b>\n\n"
            "📌 <b>أوامر استعراض الجداول:</b>\n"
            "• /schedule أو /today — جدول اليوم التفاعلي\n"
            "• /tomorrow — جدول الغد\n"
            "• /next — الحصة القادمة والجارية الآن\n"
            "• /week — الجدول الأسبوعي الكامل\n"
            "• /day <i>[اليوم]</i> — جدول يوم محدد (مثال: <code>/day الأحد</code>)\n"
            "• /lang — تغيير لغة الواجهة (عربي / English)\n\n"
            "⏰ ستصلك تنبيهات تلقائية قبل بداية كل حصة بـ 15 دقيقة في المجموعة.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_admin(update):
        return
    await update.message.reply_text(
        "🎛️ <b>لوحة تحكم المشرف</b>\nاختر الإجراء:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_main_menu(),
    )


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str | None = None) -> None:
    """عرض جدول اليوم للجميع بتصميم بطاقة حديث وتفاعلي مع دعم اللغتين."""
    user = update.effective_user
    if lang is None:
        lang = db.get_user_lang(user.id) if user else "ar"
    today_ar = get_today_name()
    sessions = db.get_sessions_by_day(today_ar)
    text = format_day_schedule(today_ar, sessions, is_today=True, lang=lang)
    keyboard = day_schedule_keyboard(today_ar, lang=lang)
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


async def cmd_full_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str | None = None) -> None:
    """عرض لوحة ملخص الجدول الأسبوعي الكامل مع أزرار تصفح الأيام مع دعم اللغتين."""
    user = update.effective_user
    if lang is None:
        lang = db.get_user_lang(user.id) if user else "ar"
    sessions = db.get_all_sessions(include_cancelled=True)
    if not sessions:
        empty_msg = "📭 No sessions found in the database." if lang == "en" else "📭 لا توجد حصص محفوظة في قاعدة البيانات."
        await update.effective_message.reply_text(empty_msg)
        return

    text = format_week_overview(sessions, lang=lang)
    keyboard = week_overview_keyboard(lang=lang)
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


async def cmd_day(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str | None = None) -> None:
    """عرض جدول يوم محدد: /day الأحد أو /day tue مع دعم اللغتين."""
    user = update.effective_user
    if lang is None:
        lang = db.get_user_lang(user.id) if user else "ar"

    if not context.args:
        today_ar = get_today_name()
        sessions = db.get_sessions_by_day(today_ar)
        text = format_day_schedule(today_ar, sessions, is_today=True, lang=lang)
        keyboard = day_schedule_keyboard(today_ar, lang=lang)
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    raw_query = " ".join(context.args).strip().lower()
    day_ar = DAY_MAP.get(raw_query)
    if not day_ar:
        if lang == "en":
            err_msg = (
                "❌ Unknown day name.\n"
                "Examples: <code>/day Sunday</code>, <code>/day Monday</code>, <code>/day tue</code>"
            )
        else:
            err_msg = (
                "❌ اسم اليوم غير معروف.\n"
                "أمثلة: <code>/day الأحد</code> ، <code>/day الاثنين</code> ، <code>/day tue</code>"
            )
        await update.effective_message.reply_text(err_msg, parse_mode=ParseMode.HTML)
        return

    today_ar = get_today_name()
    is_today = (day_ar == today_ar)
    sessions = db.get_sessions_by_day(day_ar)
    text = format_day_schedule(day_ar, sessions, is_today=is_today, lang=lang)
    keyboard = day_schedule_keyboard(day_ar, lang=lang)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# ══════════════════════════════════════════════════════════════
#  معالج رفع ملف PDF
# ══════════════════════════════════════════════════════════════

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """استقبل ملف PDF من المشرف وحلّله."""
    if not await _check_admin(update):
        return

    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("❌ يرجى إرسال ملف PDF فقط.")
        return

    # إشعار بالتحميل
    status_msg: Message = await update.message.reply_text(
        "⏳ جاري تحميل وتحليل الملف، الرجاء الانتظار..."
    )

    tmp_path = None
    try:
        # تحميل الملف
        file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

        # تحليل الـ PDF
        sessions = parse_schedule_pdf(tmp_path)

        if not sessions:
            await status_msg.edit_text(
                "⚠️ لم يتمكن البوت من استخراج حصص من هذا الملف.\n"
                "تأكد من أن الملف يحتوي على جدول منظم بالحقول: "
                "المادة، اليوم، الوقت، القاعة."
            )
            return

        # مسح الجداول القديمة وحفظ الجديدة
        db.clear_all_sessions()
        saved = 0
        for s in sessions:
            try:
                db.insert_session(
                    s["subject"], s["day"], s["start_time"], s["end_time"], s["room"]
                )
                saved += 1
            except Exception as e:
                logger.warning(f"تخطي حصة بسبب: {e}")

        # إعادة جدولة التنبيهات
        scheduler = context.bot_data.get("scheduler")
        if scheduler:
            from scheduler import reschedule_all
            reschedule_all(scheduler, context.bot)

        await status_msg.edit_text(
            f"✅ <b>تم تحليل الملف بنجاح!</b>\n\n"
            f"📊 حصص مستخرجة: {len(sessions)}\n"
            f"💾 محفوظة في قاعدة البيانات: {saved}\n"
            f"⏰ تم جدولة التنبيهات تلقائياً.",
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.exception("خطأ في معالجة PDF")
        await status_msg.edit_text(f"❌ حدث خطأ: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ══════════════════════════════════════════════════════════════
#  دوال بناء نصوص لوحات الإعدادات
# ══════════════════════════════════════════════════════════════

def _render_settings_hub_text() -> str:
    """بناء نص لوحة الإعدادات الشاملة (Hub)."""
    trans_topic = db.get_setting("translate_topic_id", "0")
    trans_desc = f"الموضوع #{trans_topic}" if trans_topic and trans_topic != "0" else "كافة المواضيع (عام) 🌐"
    is_trans_on = db.get_setting("translate_enabled", "1") == "1"
    trans_status = "شغالة 🟢" if is_trans_on else "متوقفة ⏸️"

    from scheduler import get_target_chat_and_topic
    target_chat, sched_topic = get_target_chat_and_topic()
    sched_desc = f"الموضوع #{sched_topic}" if sched_topic else "المحادثة العامة (بدون توبيك)"
    is_alerts_on = db.get_setting("alerts_enabled", "1") == "1"
    alerts_status = "مفعّلة 🟢" if is_alerts_on else "متوقفة ⏸️"

    gemini_key = db.get_setting("gemini_api_key") or GEMINI_API_KEY
    if gemini_key:
        masked = gemini_key[:6] + "..." + gemini_key[-4:] if len(gemini_key) > 10 else "متوفر ✅"
        gemini_status = f"مربوط بنجاح 🟢 (<code>{masked}</code>)"
    else:
        gemini_status = "غير مضبوط (يستخدم محرك Google المباشر مجاناً ⚡)"

    return (
        "⚙️ <b>مركز الإعدادات الشامل للبوت</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 <b>1. توبيك الترجمة الفورية:</b>\n"
        f"• الوجهة: <b>{trans_desc}</b>\n"
        f"• الحالة: <b>{trans_status}</b>\n\n"
        "📅 <b>2. توبيك إرسال جداول الحصص:</b>\n"
        f"• الوجهة: <b>{sched_desc}</b>\n"
        f"• التنبيهات: <b>{alerts_status}</b>\n\n"
        "✨ <b>3. محرك الترجمة الذكي (Gemini AI):</b>\n"
        f"• الحالة: {gemini_status}\n\n"
        "👇 <i>اختر القسم الذي تريد ضبطه من الأزرار أدناه:</i>"
    )


def _render_translate_settings_text() -> str:
    """بناء نص لوحة إعدادات توبيك الترجمة وخيارات اللغات."""
    trans_topic = db.get_setting("translate_topic_id", "0")
    topic_desc = f"الموضوع #{trans_topic}" if trans_topic and trans_topic != "0" else "كافة المواضيع (عام) 🌐"
    is_on = db.get_setting("translate_enabled", "1") == "1"
    status_label = "شغالة 🟢" if is_on else "متوقفة ⏸️"

    curr_lang = db.get_setting("translate_target_lang", "auto")
    if curr_lang == "en":
        lang_desc = "إلى الإنجليزية 🇬🇧 (عربي ➡️ EN)"
    elif curr_lang == "ar":
        lang_desc = "إلى العربية 🇸🇦 (EN ➡️ عربي)"
    else:
        lang_desc = "ثنائي الاتجاه 🔄 (عربي ↔️ إنجليزي تلقائياً)"

    gemini_key = db.get_setting("gemini_api_key") or GEMINI_API_KEY
    engine = "Google Gemini 3.6 Flash ✨" if gemini_key else "Google GTX (مباشر ومجاني) ⚡"

    return (
        "🌐 <b>إعدادات توبيك الترجمة الفورية</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>حالة الخدمة:</b> <b>{status_label}</b>\n"
        f"🗣️ <b>اتجاه الترجمة:</b> <b>{lang_desc}</b>\n"
        f"📌 <b>توبيك الترجمة الحالي:</b> <code>{topic_desc}</code>\n"
        f"🤖 <b>المحرك الفعّال:</b> <b>{engine}</b>\n\n"
        "💡 <b>الخيارات المتاحة في القائمة أدناه:</b>\n"
        "• <b>🇬🇧 إنجليزي / 🇸🇦 عربي / 🔄 ثنائي:</b> اختيار لغة وجهة الترجمة.\n"
        "• <b>تشغيل / إيقاف:</b> تفعيل أو تعطيل الترجمة.\n"
        "• <b>قفل على هذا التوبك:</b> الترجمة تعمل فقط في التوبك الحالي.\n"
        "• <b>تفعيل في كل التوبكات:</b> ترجمة الرسائل في كافة توبكات المجموعة.\n"
        "• <b>إدخال رقم يدوي:</b> تحديد رقم Topic ID يدوياً."
    )


def _render_schedule_settings_text() -> str:
    """بناء نص لوحة إعدادات توبيك إرسال الحصص."""
    from scheduler import get_target_chat_and_topic
    target_chat, sched_topic = get_target_chat_and_topic()
    sched_desc = f"الموضوع #{sched_topic}" if sched_topic else "المحادثة العامة (بدون توبيك)"
    is_alerts_on = db.get_setting("alerts_enabled", "1") == "1"
    alerts_status = "مفعّلة 🟢" if is_alerts_on else "متوقفة ⏸️"

    return (
        "📅 <b>إعدادات توبيك إرسال الحصص والتنبيهات</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 <b>حالة التنبيهات التلقائية:</b> <b>{alerts_status}</b>\n"
        f"📌 <b>وجهة التنبيهات (Topic ID):</b> <code>{sched_desc}</code>\n"
        f"💬 <b>معرّف المحادثة (Chat ID):</b> <code>{target_chat}</code>\n"
        f"⏱️ <b>وقت التنبيه:</b> قبل بداية كل حصة بـ {REMINDER_MINUTES_BEFORE} دقيقة\n\n"
        "💡 <b>الخيارات المتاحة:</b>\n"
        "• <b>تشغيل / إيقاف:</b> تفعيل أو إيقاف إرسال تنبيهات الحصص.\n"
        "• <b>قفل على هذا التوبك:</b> إرسال التنبيهات داخل التوبك الحالي حصراً.\n"
        "• <b>إدخال رقم يدوي:</b> كتابة رقم الموضوع مباشرة.\n"
        "• <b>تنبيه تجريبي:</b> إرسال تنبيه فوري للتأكد من وصوله."
    )


def _render_gemini_settings_text() -> str:
    """بناء نص لوحة إعدادات Gemini API."""
    gemini_key = db.get_setting("gemini_api_key") or GEMINI_API_KEY
    if gemini_key:
        masked = gemini_key[:6] + "..." + gemini_key[-4:] if len(gemini_key) > 10 else "متوفر ✅"
        status = f"مفعّل ومربوط بنجاح 🟢 (<code>{masked}</code>)"
    else:
        status = "غير مضبوط ⚠️ (البوت يعمل عبر محرك Google الاحتياطي المجاني)"

    return (
        "✨ <b>إعدادات محرك الترجمة الذكي (Google Gemini AI)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>حالة المفتاح:</b> {status}\n"
        "🧠 <b>الموديل الفعّال:</b> gemini-3.6-flash ✨\n\n"
        "💡 <b>المزايا:</b>\n"
        "• ترجمة سياقية ذكية للمصطلحات الأكاديمية والجامعية.\n"
        "• الحفاظ على الإيموجيات وتنسيق الرسائل بدقة تامة.\n"
        "• في حال عدم توفر المفتاح، يستمر البوت في العمل مجاناً وبدون توقف."
    )


# ══════════════════════════════════════════════════════════════
#  معالج أزرار لوحة التحكم (Callback Query)
# ══════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"تعذر الرد على استعلام الزر (الشبكة): {e}")

    data = query.data

    # ── أزرار عامة متاحة لجميع الطلاب لتصفح الجداول التفاعلية ────────
    if data.startswith("ui_lang:"):
        tokens = data.split(":")
        target_lang = tokens[1]
        db.set_user_lang(query.from_user.id, target_lang)

        toast = "🇬🇧 Switched to English!" if target_lang == "en" else "🇸🇦 تم التبديل إلى العربية!"
        try:
            await query.answer(toast)
        except Exception:
            pass

        view_type = tokens[-1]
        if view_type == "day":
            raw_day = tokens[2] if len(tokens) >= 4 else get_today_name()
            day = DAY_MAP.get(raw_day.lower(), raw_day)
            today_ar = get_today_name()
            is_today = (day == today_ar)
            sessions = db.get_sessions_by_day(day)
            text = format_day_schedule(day, sessions, is_today=is_today, lang=target_lang)
            keyboard = day_schedule_keyboard(day, lang=target_lang)
            try:
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            except Exception:
                pass
        elif view_type == "week":
            sessions = db.get_all_sessions(include_cancelled=True)
            text = format_week_overview(sessions, lang=target_lang)
            keyboard = week_overview_keyboard(lang=target_lang)
            try:
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            except Exception:
                pass
        elif view_type == "next":
            now = get_current_datetime()
            today_ar = get_today_name()
            sessions = db.get_sessions_by_day(today_ar)
            current_time_str = now.strftime("%H:%M")
            current_running = None
            upcoming = []
            for s in sessions:
                if s["start_time"] <= current_time_str <= s["end_time"]:
                    current_running = s
                elif s["start_time"] > current_time_str:
                    upcoming.append(s)
            tomorrow_ar = get_tomorrow_name()
            tomorrow_sessions = db.get_sessions_by_day(tomorrow_ar)
            tomorrow_first = tomorrow_sessions[0] if tomorrow_sessions else None

            text = format_next_card(current_running, upcoming, tomorrow_first, today_ar, lang=target_lang)
            keyboard = next_session_keyboard(lang=target_lang)
            try:
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            except Exception:
                pass
        return

    elif data.startswith("set_lang:"):
        chosen_lang = data.split(":")[1]
        db.set_user_lang(query.from_user.id, chosen_lang)
        if chosen_lang == "en":
            msg = (
                "✅ <b>Interface language set to English!</b> 🇬🇧\n\n"
                "All schedule cards and buttons will now be presented in English.\n"
                "You can switch back anytime using /lang or the button on any schedule card."
            )
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📅 Today's Schedule", callback_data="btn:today:en"),
                    InlineKeyboardButton("📋 Week Overview", callback_data="btn:week:en"),
                ],
                [
                    InlineKeyboardButton("⏭️ Next Session", callback_data="btn:next:en"),
                    InlineKeyboardButton("🇸🇦 الواجهة العربية", callback_data="ui_lang:ar:next"),
                ]
            ])
        else:
            msg = (
                "✅ <b>تم ضبط لغة الواجهة إلى العربية!</b> 🇸🇦\n\n"
                "ستظهر الآن كافة الجداول وأزرار التصفح باللغة العربية.\n"
                "يمكنك التبديل في أي وقت باستخدام /lang أو الزر الموجود أسفل البطاقات."
            )
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📅 جدول اليوم", callback_data="btn:today:ar"),
                    InlineKeyboardButton("📋 ملخص الأسبوع", callback_data="btn:week:ar"),
                ],
                [
                    InlineKeyboardButton("⏭️ الحصة القادمة", callback_data="btn:next:ar"),
                    InlineKeyboardButton("🇬🇧 English Interface", callback_data="ui_lang:en:next"),
                ]
            ])
        try:
            await query.answer("✅")
            await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            pass
        return

    elif data.startswith("btn:today"):
        parts = data.split(":")
        lang = parts[2] if len(parts) > 2 else db.get_user_lang(query.from_user.id)
        today_ar = get_today_name()
        sessions = db.get_sessions_by_day(today_ar)
        text = format_day_schedule(today_ar, sessions, is_today=True, lang=lang)
        keyboard = day_schedule_keyboard(today_ar, lang=lang)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    elif data.startswith("btn:tomorrow"):
        parts = data.split(":")
        lang = parts[2] if len(parts) > 2 else db.get_user_lang(query.from_user.id)
        tomorrow_ar = get_tomorrow_name()
        sessions = db.get_sessions_by_day(tomorrow_ar)
        text = format_day_schedule(tomorrow_ar, sessions, is_today=False, lang=lang)
        keyboard = day_schedule_keyboard(tomorrow_ar, lang=lang)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    elif data.startswith("btn:week"):
        parts = data.split(":")
        lang = parts[2] if len(parts) > 2 else db.get_user_lang(query.from_user.id)
        sessions = db.get_all_sessions(include_cancelled=True)
        text = format_week_overview(sessions, lang=lang)
        keyboard = week_overview_keyboard(lang=lang)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    elif data.startswith("btn:next"):
        parts = data.split(":")
        lang = parts[2] if len(parts) > 2 else db.get_user_lang(query.from_user.id)
        now = get_current_datetime()
        today_ar = get_today_name()
        sessions = db.get_sessions_by_day(today_ar)
        current_time_str = now.strftime("%H:%M")

        current_running = None
        upcoming = []
        for s in sessions:
            if s["start_time"] <= current_time_str <= s["end_time"]:
                current_running = s
            elif s["start_time"] > current_time_str:
                upcoming.append(s)

        tomorrow_ar = get_tomorrow_name()
        tomorrow_sessions = db.get_sessions_by_day(tomorrow_ar)
        tomorrow_first = tomorrow_sessions[0] if tomorrow_sessions else None

        text = format_next_card(current_running, upcoming, tomorrow_first, today_ar, lang=lang)
        keyboard = next_session_keyboard(lang=lang)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    elif data.startswith("view_day:"):
        parts = data.split(":")
        raw_day = parts[1]
        day = DAY_MAP.get(raw_day.lower(), raw_day)
        lang = parts[2] if len(parts) > 2 else db.get_user_lang(query.from_user.id)
        today_ar = get_today_name()
        is_today = (day == today_ar)
        sessions = db.get_sessions_by_day(day)
        text = format_day_schedule(day, sessions, is_today=is_today, lang=lang)
        keyboard = day_schedule_keyboard(day, lang=lang)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as e:
            logger.debug(f"تعديل الرسالة: {e}")
        return

    # ── فحص صلاحية المشرف لباقي أزرار التحكم ───────────────────────────
    if not is_admin(query.from_user.id):
        await query.answer("⛔ هذا الإجراء مخصص للمشرفين فقط.", show_alert=True)
        return

    parts = data.split(":")

    # ── القائمة الرئيسية ──────────────────────────────────────────
    if data == "menu:today":
        today_ar = get_today_name()
        sessions = db.get_sessions_by_day(today_ar)
        text = format_day_schedule(today_ar, sessions, is_today=True)
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_main_menu(),
        )

    elif data == "menu:all":
        sessions = db.get_all_sessions(include_cancelled=True)
        if not sessions:
            await query.edit_message_text("📭 لا توجد حصص.", reply_markup=admin_main_menu())
        else:
            text = format_week_overview(sessions)
            await query.edit_message_text(
                text[:4000], parse_mode=ParseMode.HTML, reply_markup=admin_main_menu()
            )

    elif data == "menu:edit":
        sessions = db.get_all_sessions(include_cancelled=True)
        if not sessions:
            await query.edit_message_text("📭 لا توجد حصص للتعديل.", reply_markup=admin_main_menu())
        else:
            await query.edit_message_text(
                "✏️ اختر الحصة التي تريد تعديلها:",
                reply_markup=sessions_keyboard(sessions, "edit"),
            )

    elif data == "menu:cancel":
        sessions = db.get_all_sessions(include_cancelled=False)
        if not sessions:
            await query.edit_message_text("📭 لا توجد حصص نشطة.", reply_markup=admin_main_menu())
        else:
            await query.edit_message_text(
                "❌ اختر الحصة التي تريد إلغاءها:",
                reply_markup=sessions_keyboard(sessions, "cancel"),
            )

    elif data == "menu:restore":
        sessions = db.get_all_sessions(include_cancelled=True)
        cancelled = [s for s in sessions if s["is_cancelled"]]
        if not cancelled:
            await query.edit_message_text("ℹ️ لا توجد حصص ملغاة.", reply_markup=admin_main_menu())
        else:
            await query.edit_message_text(
                "♻️ اختر الحصة التي تريد استعادتها:",
                reply_markup=sessions_keyboard(cancelled, "restore"),
            )

    elif data == "menu:delete":
        sessions = db.get_all_sessions(include_cancelled=True)
        if not sessions:
            await query.edit_message_text("📭 لا توجد حصص.", reply_markup=admin_main_menu())
        else:
            await query.edit_message_text(
                "🗑️ اختر الحصة التي تريد حذفها نهائياً:",
                reply_markup=sessions_keyboard(sessions, "delete"),
            )

    elif data == "menu:admins":
        await _handle_admins_menu(query, context)

    # ── مركز الإعدادات الشامل للبوت ───────────────────────────────
    elif data in ("menu:settings", "settings:hub"):
        await query.edit_message_text(
            _render_settings_hub_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=settings_menu_keyboard(),
        )

    # ── 1. القائمة الفرعية: إعدادات توبيك الترجمة ──────────────────
    elif data == "settings:translate":
        await query.edit_message_text(
            _render_translate_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=translate_settings_keyboard(),
        )

    elif data == "trans:toggle":
        curr = db.get_setting("translate_enabled", "1")
        new_val = "0" if curr == "1" else "1"
        db.set_setting("translate_enabled", new_val)
        status_txt = "🟢 تم تفعيل الترجمة!" if new_val == "1" else "⏸️ تم إيقاف الترجمة!"
        try:
            await query.answer(status_txt)
        except Exception:
            pass
        await query.edit_message_text(
            _render_translate_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=translate_settings_keyboard(),
        )

    elif data.startswith("trans:lang:"):
        new_lang = data.split(":")[-1]  # "en", "ar", "auto"
        db.set_setting("translate_target_lang", new_lang)
        names = {
            "en": "🇬🇧 تم تعيين الترجمة إلى الإنجليزية (عربي ➡️ EN)",
            "ar": "🇸🇦 تم تعيين الترجمة إلى العربية (EN ➡️ عربي)",
            "auto": "🔄 تم تفعيل الترجمة ثنائية الاتجاه (عربي ↔️ إنجليزي) تلقائياً",
        }
        try:
            await query.answer(names.get(new_lang, "✅ تم تغيير لغة الترجمة!"))
        except Exception:
            pass
        await query.edit_message_text(
            _render_translate_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=translate_settings_keyboard(),
        )

    elif data == "trans:lockhere":
        target_thread = getattr(query.message, "message_thread_id", None)
        if target_thread:
            db.set_setting("translate_topic_id", str(target_thread))
            try:
                await query.answer(f"✅ تم قفل الترجمة على الموضوع #{target_thread}!", show_alert=True)
            except Exception:
                pass
        else:
            db.set_setting("translate_topic_id", "0")
            try:
                await query.answer("🌐 تم تفعيل الترجمة في كل المواضيع (عام)!", show_alert=True)
            except Exception:
                pass
        await query.edit_message_text(
            _render_translate_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=translate_settings_keyboard(),
        )

    elif data == "trans:setall":
        db.set_setting("translate_topic_id", "0")
        try:
            await query.answer("🌐 تم تفعيل الترجمة في كافة التوبكات والمواضيع!", show_alert=True)
        except Exception:
            pass
        await query.edit_message_text(
            _render_translate_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=translate_settings_keyboard(),
        )

    elif data == "trans:custom_id":
        context.user_data["waiting_for_translate_topic"] = True
        try:
            await query.answer("✏️ أرسل رقم التوبك في الشات الآن")
        except Exception:
            pass
        await query.message.reply_text(
            "✏️ <b>إدخال رقم توبيك الترجمة يدوياً:</b>\n"
            "أرسل الآن رقم الـ Topic ID المطلوب (مثال: <code>3</code>),\n"
            "أو أرسل <code>0</code> لتفعيل الترجمة في كافة التوبكات.",
            parse_mode=ParseMode.HTML,
        )

    # ── 2. القائمة الفرعية: إعدادات توبيك إرسال الحصص ───────────────
    elif data == "settings:schedule":
        await query.edit_message_text(
            _render_schedule_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=schedule_topic_settings_keyboard(),
        )

    elif data == "sched:toggle_alerts":
        curr = db.get_setting("alerts_enabled", "1")
        new_val = "0" if curr == "1" else "1"
        db.set_setting("alerts_enabled", new_val)
        status_txt = "🟢 تم تفعيل تنبيهات الحصص!" if new_val == "1" else "⏸️ تم إيقاف تنبيهات الحصص!"
        try:
            await query.answer(status_txt)
        except Exception:
            pass
        await query.edit_message_text(
            _render_schedule_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=schedule_topic_settings_keyboard(),
        )

    elif data == "sched:lockhere":
        target_thread = getattr(query.message, "message_thread_id", None)
        target_chat = query.message.chat_id
        db.set_setting("group_chat_id", str(target_chat))
        if target_thread:
            db.set_setting("topic_id", str(target_thread))
            try:
                await query.answer(f"✅ تم قفل إرسال الحصص على الموضوع #{target_thread}!", show_alert=True)
            except Exception:
                pass
        else:
            db.set_setting("topic_id", "0")
            try:
                await query.answer("✅ تم قفل إرسال الحصص على هذه المجموعة (بدون توبيك)!", show_alert=True)
            except Exception:
                pass
        await query.edit_message_text(
            _render_schedule_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=schedule_topic_settings_keyboard(),
        )

    elif data == "sched:custom_id":
        context.user_data["waiting_for_schedule_topic"] = True
        try:
            await query.answer("✏️ أرسل رقم التوبك في الشات الآن")
        except Exception:
            pass
        await query.message.reply_text(
            "✏️ <b>إدخال رقم توبيك الحصص والتنبيهات:</b>\n"
            "أرسل الآن رقم الـ Topic ID المطلوب لإرسال تنبيهات الحصص فيه (مثال: <code>4</code>),\n"
            "أو أرسل <code>0</code> للإرسال في المحادثة العامة بدون توبيك.",
            parse_mode=ParseMode.HTML,
        )

    elif data == "sched:test_alert":
        sessions = db.get_all_sessions(include_cancelled=False)
        if not sessions:
            try:
                await query.answer("❌ لا توجد حصص نشطة لإرسال تنبيه تجريبي.", show_alert=True)
            except Exception:
                pass
        else:
            from scheduler import send_alert
            try:
                await send_alert(context.bot, sessions[0]["id"])
                await query.answer("🚀 تم إرسال تنبيه تجريبي بنجاح إلى التوبيك المحدد!", show_alert=True)
            except Exception as e:
                await query.answer(f"❌ تعذر الإرسال: {e}", show_alert=True)

    # ── 3. القائمة الفرعية: إعدادات Gemini AI ───────────────────────
    elif data == "settings:gemini":
        await query.edit_message_text(
            _render_gemini_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=gemini_settings_keyboard(),
        )

    elif data == "gemini:set_key":
        context.user_data["waiting_for_gemini_key"] = True
        try:
            await query.answer("🔑 أرسل المفتاح في الشات الآن")
        except Exception:
            pass
        await query.message.reply_text(
            "🔑 <b>إدخال مفتاح Google Gemini API:</b>\n\n"
            "أرسل مفتاح الـ API الخاص بك الآن (يبدأ عادةً بـ <code>AIzaSy...</code>).\n"
            "🔒 <i>سيتم حذف رسالتك تلقائياً بعد الحفظ للحفاظ على خصوصيتك وأمان المفتاح.</i>\n\n"
            "💡 للحصول على مفتاح مجاني: قم بزيارة <a href='https://aistudio.google.com/'>Google AI Studio</a>.",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    elif data == "gemini:clear_key":
        db.set_setting("gemini_api_key", "")
        try:
            await query.answer("🗑️ تم حذف مفتاح Gemini! سيعمل المحرك المجاني الاحتياطي.", show_alert=True)
        except Exception:
            pass
        await query.edit_message_text(
            _render_gemini_settings_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=gemini_settings_keyboard(),
        )

    elif data == "gemini:test":
        gemini_key = db.get_setting("gemini_api_key") or GEMINI_API_KEY
        if not gemini_key:
            try:
                await query.answer("⚠️ لا يوجد مفتاح Gemini محفوظ لتجربته. يرجى إدخال مفتاح أولاً.", show_alert=True)
            except Exception:
                pass
        else:
            test_phrase = "مرحباً بكم، الجدول الدراسي محدث وجاهز."
            res = translate_with_gemini(test_phrase, gemini_key)
            if res:
                try:
                    await query.answer(f"✅ فحص ناجح بـ Gemini!\n«{res}»", show_alert=True)
                except Exception:
                    pass
            else:
                try:
                    await query.answer("❌ تعذر الاتصال بـ Gemini API. تأكد من صلاحية المفتاح والاتصال.", show_alert=True)
                except Exception:
                    pass

    elif data == "menu:upload":
        await query.edit_message_text(
            "📤 أرسل ملف PDF الجدول الدراسي الآن.\n"
            "⚠️ سيتم استبدال الجدول الحالي بالجدول الجديد.",
        )

    elif data == "menu:back":
        await query.edit_message_text(
            "🎛️ <b>لوحة تحكم المشرف</b>\nاختر الإجراء:",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_main_menu(),
        )

    # ── تعديل الحصة (اختيار الحصة) ──────────────────────────────
    elif parts[0] == "edit" and parts[1] == "session":
        session_id = int(parts[2])
        s = db.get_session(session_id)
        await query.edit_message_text(
            f"✏️ تعديل الحصة:\n"
            f"📚 {s['subject']} | {s['day']} {s['start_time']}–{s['end_time']}\n"
            f"📍 {s['room']}\n\nاختر نوع التعديل:",
            reply_markup=edit_options_keyboard(session_id),
        )

    # ── تعديل الغرفة ─────────────────────────────────────────────
    elif parts[0] == "edit" and parts[1] == "room":
        session_id = int(parts[2])
        await query.edit_message_text(
            "🏫 اختر نوع الغرفة:",
            reply_markup=room_type_keyboard(session_id),
        )

    elif parts[0] == "room" and parts[1] == "cc":
        session_id = int(parts[2])
        await query.edit_message_text("🖥️ اختر غرفة CC:", reply_markup=cc_rooms_keyboard(session_id))

    elif parts[0] == "room" and parts[1] == "normal":
        session_id = int(parts[2])
        await query.edit_message_text("🏫 اختر الغرفة:", reply_markup=normal_rooms_keyboard(session_id))

    elif parts[0] == "room" and parts[1] == "amphi":
        session_id = int(parts[2])
        await query.edit_message_text("🏛️ اختر المدرج:", reply_markup=amphi_rooms_keyboard(session_id))

    elif parts[0] == "room" and parts[1] == "type":
        session_id = int(parts[2])
        await query.edit_message_text("🏫 اختر نوع الغرفة:", reply_markup=room_type_keyboard(session_id))

    elif parts[0] == "setroom":
        session_id = int(parts[1])
        new_room = ":".join(parts[2:])
        db.update_session_room(session_id, new_room)
        # إعادة الجدولة
        s = db.get_session(session_id)
        scheduler = context.bot_data.get("scheduler")
        if scheduler:
            from scheduler import schedule_session_alert
            schedule_session_alert(scheduler, context.bot, session_id, s["day"], s["start_time"])
        await query.edit_message_text(
            f"✅ تم تغيير القاعة إلى <b>{new_room}</b> بنجاح!",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_main_menu(),
        )

    # ── تعديل الوقت ──────────────────────────────────────────────
    elif parts[0] == "edit" and parts[1] == "time":
        session_id = int(parts[2])
        context.user_data["edit_time_session"] = session_id
        await query.edit_message_text(
            "⏰ أرسل الوقت الجديد بالصيغة:\n"
            "<code>HH:MM - HH:MM</code>\n"
            "مثال: <code>09:00 - 10:30</code>",
            parse_mode=ParseMode.HTML,
        )

    # ── تعديل اسم المادة ─────────────────────────────────────────
    elif parts[0] == "edit" and parts[1] == "subject":
        session_id = int(parts[2])
        context.user_data["edit_subject_session"] = session_id
        await query.edit_message_text(
            "📝 أرسل الاسم الجديد للمادة:"
        )

    # ── إلغاء حصة ────────────────────────────────────────────────
    elif parts[0] == "cancel" and parts[1] == "session":
        session_id = int(parts[2])
        s = db.get_session(session_id)
        await query.edit_message_text(
            f"❌ هل تريد إلغاء الحصة التالية؟\n"
            f"📚 {s['subject']} | {s['day']} {s['start_time']}–{s['end_time']}",
            reply_markup=confirm_keyboard("cancel", session_id),
        )

    # ── استعادة حصة ──────────────────────────────────────────────
    elif parts[0] == "restore" and parts[1] == "session":
        session_id = int(parts[2])
        s = db.get_session(session_id)
        await query.edit_message_text(
            f"♻️ هل تريد استعادة الحصة التالية؟\n"
            f"📚 {s['subject']} | {s['day']} {s['start_time']}–{s['end_time']}",
            reply_markup=confirm_keyboard("restore", session_id),
        )

    # ── حذف نهائي ────────────────────────────────────────────────
    elif parts[0] == "delete" and parts[1] == "session":
        session_id = int(parts[2])
        s = db.get_session(session_id)
        await query.edit_message_text(
            f"⚠️ هل تريد حذف هذه الحصة نهائياً؟\n"
            f"📚 {s['subject']} | {s['day']} {s['start_time']}–{s['end_time']}\n\n"
            "⚠️ <b>لا يمكن التراجع عن هذه العملية!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=confirm_keyboard("delete", session_id),
        )

    # ── تأكيد الإجراءات ──────────────────────────────────────────
    elif parts[0] == "confirm":
        action     = parts[1]
        session_id = int(parts[2])
        scheduler  = context.bot_data.get("scheduler")

        if action == "cancel":
            db.cancel_session(session_id)
            if scheduler:
                from scheduler import unschedule_session
                unschedule_session(scheduler, session_id)
            await query.edit_message_text(
                "✅ تم إلغاء الحصة. لن تُرسَل تنبيهات لهذه الحصة.",
                reply_markup=admin_main_menu(),
            )

        elif action == "restore":
            db.restore_session(session_id)
            s = db.get_session(session_id)
            if scheduler:
                from scheduler import schedule_session_alert
                schedule_session_alert(scheduler, context.bot, session_id, s["day"], s["start_time"])
            await query.edit_message_text(
                "✅ تمت استعادة الحصة وإعادة جدولة التنبيه.",
                reply_markup=admin_main_menu(),
            )

        elif action == "delete":
            if scheduler:
                from scheduler import unschedule_session
                unschedule_session(scheduler, session_id)
            db.delete_session(session_id)
            await query.edit_message_text(
                "🗑️ تم حذف الحصة نهائياً.",
                reply_markup=admin_main_menu(),
            )


# ══════════════════════════════════════════════════════════════
#  معالج الرسائل النصية (لإدخال البيانات التفاعلي)
# ══════════════════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_message.text:
        return

    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    user_data = context.user_data
    text = msg.text.strip()

    # تسجيل المستخدم في قاعدة البيانات لتحديث الاسم والمعرّف تلقائياً
    if user and not user.is_bot:
        db.upsert_member(user.id, user.username, user.full_name or user.first_name)

    # ── انتظار إدخال رقم توبيك الترجمة ─────────────────────────────
    if user_data.get("waiting_for_translate_topic"):
        user_data.pop("waiting_for_translate_topic", None)
        try:
            tid = int(text)
            db.set_setting("translate_topic_id", str(tid))
            desc = f"الموضوع رقم #{tid}" if tid != 0 else "كافة المواضيع (عام) 🌐"
            await msg.reply_text(f"✅ <b>تم ضبط توبيك الترجمة بنجاح!</b>\nالوجهة الحالية: <b>{desc}</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await msg.reply_text("❌ يرجى إرسال رقم صحيح للتوبك (مثال: 3، أو 0 للعام).")
        return

    # ── انتظار إدخال رقم توبيك الحصص ────────────────────────────────
    if user_data.get("waiting_for_schedule_topic"):
        user_data.pop("waiting_for_schedule_topic", None)
        try:
            tid = int(text)
            db.set_setting("topic_id", str(tid))
            desc = f"الموضوع رقم #{tid}" if tid != 0 else "المحادثة العامة (بدون توبيك)"
            await msg.reply_text(f"✅ <b>تم ضبط توبيك إرسال الحصص والتنبيهات بنجاح!</b>\nالوجهة الحالية: <b>{desc}</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await msg.reply_text("❌ يرجى إرسال رقم صحيح للتوبك (مثال: 4، أو 0 للعام).")
        return

    # ── انتظار إدخال مفتاح Gemini API ───────────────────────────────
    if user_data.get("waiting_for_gemini_key"):
        user_data.pop("waiting_for_gemini_key", None)
        new_key = text.strip()
        try:
            await msg.delete()
        except Exception:
            pass

        test_res = translate_with_gemini("مرحباً بكم جميعاً", new_key)
        if test_res:
            db.set_setting("gemini_api_key", new_key)
            await chat.send_message(
                f"✅ <b>تم حفظ وتفعيل مفتاح Google Gemini AI بنجاح!</b>\n\n"
                f"🧪 <b>نتيجة الاختبار التجريبي:</b>\n"
                f"«مرحباً بكم جميعاً» ➡️ «<code>{test_res}</code>»\n\n"
                f"✨ ستتم الآن جميع الترجمات في البوت عبر الذكاء الاصطناعي بدقة فائقة.",
                parse_mode=ParseMode.HTML,
            )
        else:
            db.set_setting("gemini_api_key", new_key)
            await chat.send_message(
                "⚠️ <b>تم حفظ المفتاح بنجاح!</b>\n"
                "لكن تعذر استلام استجابة فورية أثناء الاختبار. سيعمل البوت بـ Gemini مع التبديل التلقائي للمحرك الاحتياطي عند الحاجة.",
                parse_mode=ParseMode.HTML,
            )
        return

    # ── 1. تعديل الوقت ───────────────────────────────────────────
    if "edit_time_session" in user_data:
        session_id = user_data.pop("edit_time_session")
        parts = [p.strip() for p in text.replace("–", "-").replace("—", "-").split("-")]
        if len(parts) == 2:
            start_time, end_time = parts[0], parts[1]
            import re
            if re.match(r"^\d{2}:\d{2}$", start_time) and re.match(r"^\d{2}:\d{2}$", end_time):
                db.update_session_time(session_id, start_time, end_time)
                s = db.get_session(session_id)
                scheduler = context.bot_data.get("scheduler")
                if scheduler:
                    from scheduler import schedule_session_alert
                    schedule_session_alert(scheduler, context.bot, session_id, s["day"], start_time)
                await update.message.reply_text(
                    f"✅ تم تعديل وقت الحصة إلى {start_time} - {end_time}",
                    reply_markup=admin_main_menu(),
                )
                return
        await update.message.reply_text(
            "❌ صيغة غير صحيحة. أرسل بالشكل: <code>09:00 - 10:30</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # ── 2. تعديل اسم المادة ───────────────────────────────────────
    elif "edit_subject_session" in user_data:
        session_id = user_data.pop("edit_subject_session")
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET subject=?, updated_at=datetime('now') WHERE id=?",
                (text, session_id),
            )
        await update.message.reply_text(
            f"✅ تم تغيير اسم المادة إلى: <b>{text}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_main_menu(),
        )
        return

    logger.info(f"📩 رسالة مستلمة في شات {chat.id} ({chat.type}, توبيك: {msg.message_thread_id}): {text[:50]}")

    # ── 3. ميزة الترجمة التلقائية ────────────────────────────────
    translate_enabled = db.get_setting("translate_enabled", "1")
    if translate_enabled == "1":
        # في المحادثات الخاصة مع البوت: يترجم دائماً
        is_private = chat and chat.type == "private"

        # في المجموعات: فحص مطابقة رقم الموضوع (Topic)
        current_thread_id = getattr(msg, "message_thread_id", None)
        if not is_private:
            configured_topic = db.get_setting("translate_topic_id", "0")

            # إذا حُدد موضوع معين (وليس 0 للكل) ولم تتطابق الرسالة معه، نتجاهلها
            if configured_topic and configured_topic != "0":
                try:
                    target_thread_id = int(configured_topic)
                except ValueError:
                    target_thread_id = None
                if target_thread_id is not None and current_thread_id != target_thread_id:
                    logger.debug(f"تخطي الترجمة: توبك الرسالة ({current_thread_id}) ليس التوبك المضبوط ({target_thread_id})")
                    return

        # تنظيف منشن البوت إن وُجد (مثلاً: @bot ترجمة)
        import re
        clean_text = re.sub(r"@\w+_bot\b", "", text, flags=re.IGNORECASE).strip()
        if not clean_text:
            return

        target_mode = db.get_setting("translate_target_lang", "auto")

        # فحص احتواء النص على حروف عربية أو إنجليزية
        has_ar = bool(re.search(r"[\u0600-\u06FF]", clean_text))
        has_en = bool(re.search(r"[a-zA-Z]", clean_text))

        # تصفية حسب اتجاه الترجمة المحدد
        if target_mode == "en" and not has_ar:
            return  # المطلوب إنجليزي فقط والنص لا يحتوي على عربي
        elif target_mode == "ar" and not has_en:
            return  # المطلوب عربي فقط والنص لا يحتوي على إنجليزي
        elif not has_ar and not has_en:
            return  # نص أرقام أو رموز فقط

        # ترجمة النص عبر المحرك الذكي (Gemini 3.6 Flash)
        translated, target_code = translate_text(clean_text, target_mode=target_mode)
        if not translated or translated.strip().lower() == clean_text.strip().lower():
            return

        flag = "🇬🇧" if target_code == "en" else "🇸🇦"
        reply_text = f"{flag} {translated}"

        try:
            await msg.reply_text(
                reply_text,
                message_thread_id=current_thread_id,
                allow_sending_without_reply=True,
                disable_web_page_preview=True,
            )
            logger.info(f"✅ تمت الترجمة بنجاح ({clean_text} -> {translated}) في شات {chat.id} (توبيك {current_thread_id})")
        except Exception as e:
            logger.warning(f"⚠️ تعذر reply_text: {e}، محاولة الإرسال كرسالة جديدة في التوبك...")
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    message_thread_id=current_thread_id,
                    text=reply_text,
                    disable_web_page_preview=True,
                )
                logger.info(f"✅ تم إرسال الترجمة بنجاح عبر send_message في شات {chat.id}")
            except Exception as e2:
                logger.error(f"❌ فشل إرسال الترجمة في المجموعة: {e2}")


# ══════════════════════════════════════════════════════════════
#  معالج انضمام/مغادرة الأعضاء
# ══════════════════════════════════════════════════════════════

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    for member in update.message.new_chat_members:
        if not member.is_bot:
            db.upsert_member(member.id, member.username, member.full_name or member.first_name)
            logger.info(f"👤 عضو جديد مسجّل: {member.full_name} ({member.id})")


async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    member = update.message.left_chat_member
    if member and not member.is_bot:
        db.remove_member(member.id)
        logger.info(f"👋 عضو غادر وحُذف: {member.full_name} ({member.id})")


# ══════════════════════════════════════════════════════════════
#  إدارة المشرفين
# ══════════════════════════════════════════════════════════════

async def _handle_admins_menu(query, context) -> None:
    db_admins = db.get_db_admins()
    config_admins = ADMIN_IDS
    all_admins = list(set(db_admins + config_admins))

    text = "👤 <b>المشرفون الحاليون:</b>\n\n"
    for uid in all_admins:
        source = "(config)" if uid in config_admins else "(db)"
        text += f"• <code>{uid}</code> {source}\n"
    text += "\n📌 لإضافة مشرف: <code>/addadmin USER_ID</code>\n"
    text += "📌 لإزالة مشرف: <code>/removeadmin USER_ID</code>"

    from keyboards import admin_main_menu
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=admin_main_menu())


async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_admin(update):
        return
    if not context.args:
        await update.message.reply_text("الاستخدام: /addadmin <user_id>")
        return
    try:
        new_admin_id = int(context.args[0])
        db.add_admin(new_admin_id, update.effective_user.id)
        await update.message.reply_text(f"✅ تمت إضافة المشرف: <code>{new_admin_id}</code>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ معرّف غير صحيح.")


async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_admin(update):
        return
    if not context.args:
        await update.message.reply_text("الاستخدام: /removeadmin <user_id>")
        return
    try:
        rm_id = int(context.args[0])
        if rm_id in ADMIN_IDS:
            await update.message.reply_text("⚠️ لا يمكن إزالة مشرف محدد في الـ config.")
            return
        db.remove_admin(rm_id)
        await update.message.reply_text(f"✅ تمت إزالة المشرف: <code>{rm_id}</code>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ معرّف غير صحيح.")


# ══════════════════════════════════════════════════════════════
#  الدوال المساعدة
# ══════════════════════════════════════════════════════════════

def _today_arabic() -> str:
    """أرجع اسم اليوم الحالي بالعربية وفق التوقيت المحلي."""
    return get_today_name()


def _tomorrow_arabic() -> str:
    """أرجع اسم يوم الغد بالعربية وفق التوقيت المحلي."""
    return get_tomorrow_name()


# ══════════════════════════════════════════════════════════════
#  أوامر متقدمة إضافية (Next, Tomorrow, Topics, Control)
# ══════════════════════════════════════════════════════════════

async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str | None = None) -> None:
    """معرفة الحصة القادمة والجارية الآن بناءً على التوقيت المحلي بدقة مع دعم اللغتين."""
    user = update.effective_user
    if lang is None:
        lang = db.get_user_lang(user.id) if user else "ar"
    now = get_current_datetime()
    today_ar = get_today_name()
    sessions = db.get_sessions_by_day(today_ar)
    current_time_str = now.strftime("%H:%M")

    current_running = None
    upcoming = []

    for s in sessions:
        if s["start_time"] <= current_time_str <= s["end_time"]:
            current_running = s
        elif s["start_time"] > current_time_str:
            upcoming.append(s)

    tomorrow_ar = get_tomorrow_name()
    tomorrow_sessions = db.get_sessions_by_day(tomorrow_ar)
    tomorrow_first = tomorrow_sessions[0] if tomorrow_sessions else None

    text = format_next_card(current_running, upcoming, tomorrow_first, today_ar, lang=lang)
    keyboard = next_session_keyboard(lang=lang)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def cmd_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str | None = None) -> None:
    """عرض جدول الغد بتصميم حديث وتفاعلي مع دعم اللغتين."""
    user = update.effective_user
    if lang is None:
        lang = db.get_user_lang(user.id) if user else "ar"
    tomorrow_ar = get_tomorrow_name()
    sessions = db.get_sessions_by_day(tomorrow_ar)
    text = format_day_schedule(tomorrow_ar, sessions, is_today=False, lang=lang)
    keyboard = day_schedule_keyboard(tomorrow_ar, lang=lang)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# ── أوامر سريعة محددة للغة الإنجليزية والعربية مباشرة ────────────
async def cmd_schedule_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جدول اليوم باللغة الإنجليزية مباشرة: /schedule_en أو /today_en"""
    await cmd_schedule(update, context, lang="en")


async def cmd_schedule_ar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جدول اليوم باللغة العربية مباشرة: /schedule_ar أو /today_ar"""
    await cmd_schedule(update, context, lang="ar")


async def cmd_tomorrow_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جدول الغد باللغة الإنجليزية مباشرة: /tomorrow_en"""
    await cmd_tomorrow(update, context, lang="en")


async def cmd_tomorrow_ar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جدول الغد باللغة العربية مباشرة: /tomorrow_ar"""
    await cmd_tomorrow(update, context, lang="ar")


async def cmd_full_schedule_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض الجدول الأسبوعي باللغة الإنجليزية مباشرة: /week_en أو /fullschedule_en"""
    await cmd_full_schedule(update, context, lang="en")


async def cmd_full_schedule_ar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض الجدول الأسبوعي باللغة العربية مباشرة: /week_ar أو /fullschedule_ar"""
    await cmd_full_schedule(update, context, lang="ar")


async def cmd_next_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض بطاقة الحصة القادمة باللغة الإنجليزية مباشرة: /next_en"""
    await cmd_next(update, context, lang="en")


async def cmd_next_ar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض بطاقة الحصة القادمة باللغة العربية مباشرة: /next_ar"""
    await cmd_next(update, context, lang="ar")


async def cmd_switch_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر تبديل لغة الواجهة: /lang أو /language"""
    user = update.effective_user
    current_lang = db.get_user_lang(user.id) if user else "ar"
    current_desc = "🇬🇧 English" if current_lang == "en" else "🇸🇦 العربية"

    text = (
        "🌐 <b>اختيار لغة واجهة البوت / Select Bot Interface Language</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 اللغة الحالية / Current: <b>{current_desc}</b>\n\n"
        "اختر لغة الواجهة التي تفضل ظهور الجداول والأزرار بها:\n"
        "Choose your preferred interface language below:"
    )
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=language_select_keyboard(),
    )


async def cmd_set_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تعيين الموضوع (Topic/Thread) الحالي كوجهة لإرسال التنبيهات."""
    if not await _check_admin(update):
        return

    chat = update.effective_chat
    thread_id = getattr(update.message, "message_thread_id", None)

    if context.args:
        try:
            thread_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح للتوبك: <code>/settopic 4</code>", parse_mode=ParseMode.HTML)
            return

    if not thread_id:
        await update.message.reply_text(
            "ℹ️ <b>طريقة تعيين التوبك:</b>\n"
            "1. أرسل الأمر <code>/settopic</code> داخل التوبك المطلوب مباشرة.\n"
            "2. أو حدد الرقم يدوياً: <code>/settopic 4</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    db.set_setting("group_chat_id", str(chat.id))
    db.set_setting("topic_id", str(thread_id))

    await update.message.reply_text(
        f"✅ <b>تم تعيين وجهة التنبيهات بنجاح!</b>\n\n"
        f"💬 <b>المجموعة:</b> <code>{chat.id}</code>\n"
        f"📌 <b>رقم التوبك (Topic ID):</b> <code>{thread_id}</code>\n\n"
        f"ستُرسَل التنبيهات القادمة داخل هذا التوبك حصراً.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_test_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إرسال تنبيه تجريبي فوراً للتأكد من وصوله إلى التوبك المطلوب."""
    if not await _check_admin(update):
        return

    sessions = db.get_all_sessions(include_cancelled=False)
    if not sessions:
        await update.message.reply_text("❌ لا توجد حصص في قاعدة البيانات لإرسال تنبيه تجريبي.")
        return

    first_session_id = sessions[0]["id"]
    from scheduler import send_alert
    await send_alert(context.bot, first_session_id)
    await update.message.reply_text("🚀 تم إرسال تنبيه تجريبي إلى الموضوع المحدد، تفقّد التوبك الآن!")


async def cmd_pause_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إيقاف التنبيهات مؤقتاً."""
    if not await _check_admin(update):
        return
    db.set_setting("alerts_enabled", "0")
    await update.message.reply_text("⏸️ تم إيقاف إرسال التنبيهات التلقائية مؤقتاً (مثلاً أثناء العطلة).")


async def cmd_resume_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """استئناف التنبيهات."""
    if not await _check_admin(update):
        return
    db.set_setting("alerts_enabled", "1")
    await update.message.reply_text("▶️ تم استئناف إرسال التنبيهات التلقائية بنجاح.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض إحصائيات ومعلومات حالة البوت."""
    total_sessions = len(db.get_all_sessions(include_cancelled=True))
    active_sessions = len(db.get_all_sessions(include_cancelled=False))
    members_count = len(db.get_all_members())
    status_alerts = "مفعّلة 🟢" if db.get_setting("alerts_enabled", "1") == "1" else "متوقفة ⏸️"

    from scheduler import get_target_chat_and_topic
    chat_id, topic_id = get_target_chat_and_topic()

    text = (
        f"📊 <b>إحصائيات وحالة البوت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📚 إجمالي الحصص: <b>{total_sessions}</b> (النشطة: <b>{active_sessions}</b>)\n"
        f"👥 الأعضاء المسجلين للمنشن: <b>{members_count}</b>\n"
        f"🔔 حالة التنبيهات: <b>{status_alerts}</b>\n"
        f"💬 معرّف المجموعة: <code>{chat_id}</code>\n"
        f"📌 معرّف التوبك (Topic): <code>{topic_id or 'بدون توبك (العام)'}</code>\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_seed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إعادة تعبئة الجدول الدراسي الأصلي يدوياً من داخل تيليجرام."""
    if not await _check_admin(update):
        return
    try:
        from seed_data import seed
        seed()
        scheduler = context.bot_data.get("scheduler")
        if scheduler:
            from scheduler import reschedule_all
            reschedule_all(scheduler, context.bot)
        await update.message.reply_text("✅ تم بنجاح إعادة تعبئة الجدول الدراسي (20 حصة) وإعادة جدولة كافة التنبيهات!")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء التعبئة: {e}")


# ══════════════════════════════════════════════════════════════
#  أوامر التحكم ببارامترات الترجمة والمواضيع للمشرفين
# ══════════════════════════════════════════════════════════════

async def cmd_set_translate_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تحديد رقم الموضوع (Topic ID) الذي ستعمل فيه الترجمة التلقائية."""
    if not await _check_admin(update):
        return

    msg = update.effective_message
    if context.args:
        try:
            thread_id = int(context.args[0])
        except ValueError:
            await msg.reply_text("❌ يرجى إدخال رقم موضوع صحيح، أو إدخال 0 للعمل في كل المواضيع.")
            return
    elif msg.message_thread_id:
        thread_id = msg.message_thread_id
    else:
        await msg.reply_text(
            "📌 <b>تحديد موضوع الترجمة:</b>\n"
            "أرسل الأمر متبوعاً برقم الموضوع، مثلاً:\n"
            "<code>/translatetopic 3</code>\n\n"
            "أو اكتب <code>/translatetopic 0</code> لتفعيل الترجمة في كل المواضيع،\n"
            "أو أرسل الأمر <code>/translatetopic</code> مباشرة داخل الموضوع المراد.",
            parse_mode=ParseMode.HTML,
        )
        return

    db.set_setting("translate_topic_id", str(thread_id))
    topic_desc = f"الموضوع رقم <b>{thread_id}</b>" if thread_id != 0 else "<b>كافة المواضيع (General & Topics)</b>"
    await msg.reply_text(
        f"✅ <b>تم ضبط موضوع الترجمة بنجاح!</b>\n"
        f"ستعمل الترجمة الحرفية والمنشن التلقائي حصراً في: {topic_desc}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_set_translate_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تشغيل أو إيقاف ميزة الترجمة التلقائية."""
    if not await _check_admin(update):
        return
    msg = update.effective_message
    if not context.args:
        current = "مفعّلة 🟢" if db.get_setting("translate_enabled", "1") == "1" else "معطّلة ⏸️"
        await msg.reply_text(
            f"حالة الترجمة الحالية: <b>{current}</b>\n\n"
            f"للتبديل أرسل:\n"
            f"<code>/translatemode on</code> للتشغيل\n"
            f"<code>/translatemode off</code> للإيقاف",
            parse_mode=ParseMode.HTML,
        )
        return

    arg = context.args[0].lower().strip()
    if arg in ("on", "1", "تشغيل", "enable"):
        db.set_setting("translate_enabled", "1")
        await msg.reply_text("🟢 تم <b>تفعيل</b> ميزة الترجمة.", parse_mode=ParseMode.HTML)
    elif arg in ("off", "0", "ايقاف", "إيقاف", "disable"):
        db.set_setting("translate_enabled", "0")
        await msg.reply_text("⏸️ تم <b>إيقاف</b> ميزة الترجمة مؤقتاً.", parse_mode=ParseMode.HTML)
    else:
        await msg.reply_text("❌ اكتب on أو off.")


async def cmd_set_translate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تحديد المستخدم المسموح له بتحفيز الترجمة."""
    if not await _check_admin(update):
        return
    msg = update.effective_message
    if not context.args:
        current_u = db.get_setting("translate_auth_username", "all")
        await msg.reply_text(
            f"المستخدم المصرح له الحالي: <b>@{current_u}</b>\n\n"
            f"لتغييره أرسل: <code>/setuser username</code> (أو <code>/setuser all</code> للجميع)",
            parse_mode=ParseMode.HTML,
        )
        return

    new_user = context.args[0].strip().lstrip("@")
    db.set_setting("translate_auth_username", new_user)
    desc = f"@{new_user}" if new_user != "all" else "الجميع"
    await msg.reply_text(f"✅ تم تعيين المستخدم المصرح له بالترجمة: <b>{desc}</b>", parse_mode=ParseMode.HTML)


async def cmd_bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض مركز إعدادات الترجمة والحصص التفاعلي الشامل."""
    if not await _check_admin(update):
        return

    text = _render_settings_hub_text()
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=settings_menu_keyboard(),
    )


async def cmd_set_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إدخال أو فحص مفتاح Gemini API للمشرف: /setgemini [api_key]"""
    if not await _check_admin(update):
        return
    msg = update.effective_message
    if not context.args:
        gemini_key = db.get_setting("gemini_api_key") or GEMINI_API_KEY
        if gemini_key:
            masked = gemini_key[:6] + "..." + gemini_key[-4:] if len(gemini_key) > 10 else "متوفر ✅"
            await msg.reply_text(
                f"🔑 <b>مفتاح Gemini API الحالي:</b> <code>{masked}</code>\n\n"
                f"لتحديثه أرسل: <code>/setgemini YOUR_API_KEY</code>\n"
                f"أو استخدم لوحة الإعدادات التفاعلية: /settings",
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.reply_text(
                "ℹ️ <b>لم يتم ضبط مفتاح Gemini API بعد.</b>\n\n"
                "لتحديده أرسل: <code>/setgemini YOUR_API_KEY</code>\n"
                "أو ادخل على لوحة الإعدادات: /settings",
                parse_mode=ParseMode.HTML,
            )
        return

    new_key = context.args[0].strip()
    test_res = translate_with_gemini("مرحباً بكم", new_key)
    if test_res:
        db.set_setting("gemini_api_key", new_key)
        await msg.reply_text(
            f"✅ <b>تم تفعيل مفتاح Google Gemini بنجاح!</b>\n"
            f"🧪 نتيجة الاختبار: «<code>{test_res}</code>»",
            parse_mode=ParseMode.HTML,
        )
    else:
        db.set_setting("gemini_api_key", new_key)
        await msg.reply_text(
            "⚠️ تم حفظ المفتاح في قاعدة البيانات. (تعذر استلام نتيجة الاختبار فوراً، تأكد من صحة المفتاح)",
            parse_mode=ParseMode.HTML,
        )


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ترجمة فورية لأي نص أو رد على رسالة: /tr أو /trad أو /translate"""
    msg = update.effective_message
    if not msg:
        return

    target_text = ""
    if msg.reply_to_message:
        target_text = (msg.reply_to_message.text or msg.reply_to_message.caption or "").strip()
    elif context.args:
        target_text = " ".join(context.args).strip()

    if not target_text:
        await msg.reply_text(
            "ℹ️ <b>طريقة الترجمة الفورية:</b>\n"
            "• اكتب <code>/tr مرحباً</code> أو <code>/trad أي نص</code>\n"
            "• أو قم بالرد (Reply) على أي رسالة واكتب <code>/tr</code> أو <code>/trad</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    target_mode = db.get_setting("translate_target_lang", "auto")
    translated, target_code = translate_text(target_text, target_mode=target_mode)
    if not translated or translated.strip().lower() == target_text.strip().lower():
        await msg.reply_text("⚠️ لم يتغير النص أو تعذرت الترجمة.")
        return

    flag = "🇬🇧" if target_code == "en" else "🇸🇦"
    await msg.reply_text(f"{flag} {translated}")





