"""
handlers.py - جميع معالجات الأوامر والأزرار التفاعلية
"""
import logging
import os
import tempfile
from datetime import datetime

from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database as db
from config import ADMIN_IDS, ALL_ROOMS, DAY_MAP
from keyboards import (
    admin_main_menu,
    sessions_keyboard,
    edit_options_keyboard,
    room_type_keyboard,
    cc_rooms_keyboard,
    normal_rooms_keyboard,
    amphi_rooms_keyboard,
    confirm_keyboard,
)
from pdf_parser import parse_schedule_pdf

logger = logging.getLogger(__name__)


def translate_ar_to_en(text: str) -> str:
    """ترجمة دقيقة وسريعة من العربية إلى الإنجليزية بدون قيود ولا حظر."""
    if not text or not text.strip():
        return ""

    raw_text = text.strip()

    # 1. المحرك الأساسي: Google Chrome Extension API المباشر (سريع جداً، موثوق، لا يحظر إطلاقاً)
    try:
        import urllib.request
        import urllib.parse
        import json
        encoded_query = urllib.parse.quote(raw_text)
        url = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=en&q={encoded_query}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                parts = [item[0] for item in data if isinstance(item, list) and item and item[0]]
                if parts:
                    return " ".join(parts).strip()
    except Exception as e:
        logger.warning(f"⚠️ [Google Translate API] فشل: {e}")

    # 2. المحرك الاحتياطي: MyMemory مع البريد لرفع الحصة اليومية
    try:
        import urllib.request
        import urllib.parse
        import json
        url = "https://api.mymemory.translated.net/get?q=" + urllib.parse.quote(raw_text) + "&langpair=ar|en&de=iyeddevbot@gmail.com"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            t = res.get("responseData", {}).get("translatedText")
            if t and "MYMEMORY" not in t and t.strip() != raw_text:
                return t.strip()
    except Exception as e:
        logger.warning(f"⚠️ [MyMemory Translate] فشل: {e}")

    return raw_text


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

    if is_admin(user.id):
        await update.message.reply_text(
            f"👋 أهلاً {name}!\n\n"
            "🤖 <b>بوت إدارة الجداول الدراسية</b>\n\n"
            "يمكنك رفع ملف PDF لاستخراج الجدول تلقائياً، "
            "أو استخدام لوحة التحكم للتعديل والمتابعة.\n\n"
            "اضغط /panel للوصول إلى لوحة التحكم.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"👋 أهلاً {name}!\n\n"
            "📅 <b>بوت متابعة الجدول الدراسي</b>\n\n"
            "ستصلك تنبيهات تلقائية قبل بدء كل حصة بـ 15 دقيقة.\n"
            "استخدم /schedule لعرض الجدول الكامل.",
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


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جدول اليوم للجميع."""
    today_ar = _today_arabic()
    sessions = db.get_sessions_by_day(today_ar)

    if not sessions:
        await update.message.reply_text(
            f"📅 لا توجد حصص مجدولة اليوم ({today_ar})."
        )
        return

    lines = [f"📅 <b>جدول اليوم — {today_ar}</b>\n"]
    for s in sessions:
        status = "✅" if not s["is_cancelled"] else "❌ (ملغى)"
        lines.append(
            f"{status} <b>{s['subject']}</b>\n"
            f"   ⏰ {s['start_time']} → {s['end_time']}\n"
            f"   📍 {s['room']}\n"
        )

    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML
    )


async def cmd_full_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض الجدول الكامل للأسبوع."""
    sessions = db.get_all_sessions()
    if not sessions:
        await update.message.reply_text("📭 لا توجد حصص محفوظة في قاعدة البيانات.")
        return

    # تجميع حسب اليوم
    by_day: dict[str, list] = {}
    for s in sessions:
        by_day.setdefault(s["day"], []).append(s)

    text = "📋 <b>الجدول الأسبوعي الكامل</b>\n\n"
    for day, day_sessions in by_day.items():
        text += f"━━━ <b>{day}</b> ━━━\n"
        for s in day_sessions:
            status = "✅" if not s["is_cancelled"] else "❌"
            text += (
                f"{status} {s['start_time']}-{s['end_time']} "
                f"| {s['subject']} | {s['room']}\n"
            )
        text += "\n"

    # تقسيم الرسالة إذا كانت طويلة
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


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
#  معالج أزرار لوحة التحكم (Callback Query)
# ══════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"تعذر الرد على استعلام الزر (الشبكة): {e}")

    data = query.data

    # ── أزرار عامة متاحة لجميع الطلاب من بطاقة التنبيه ─────────────────
    if data == "btn:today":
        today_ar = _today_arabic()
        sessions = db.get_sessions_by_day(today_ar)
        if not sessions:
            await query.message.reply_text(f"📅 لا توجد حصص مجدولة اليوم (<b>{today_ar}</b>).", parse_mode=ParseMode.HTML)
            return
        lines = [f"📅 <b>جدول اليوم — {today_ar}</b>\n"]
        for s in sessions:
            st = "✅" if not s["is_cancelled"] else "❌"
            lines.append(f"{st} <b>{s['subject']}</b>\n   ⏰ <code>{s['start_time']}</code> ➔ <code>{s['end_time']}</code>  |  📍 <b>{s['room']}</b>")
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    elif data == "btn:next":
        await cmd_next(update, context)
        return

    # ── فحص صلاحية المشرف لباقي أزرار التحكم ───────────────────────────
    if not is_admin(query.from_user.id):
        await query.answer("⛔ هذا الإجراء مخصص للمشرفين فقط.", show_alert=True)
        return

    parts = data.split(":")

    # ── القائمة الرئيسية ──────────────────────────────────────────
    if data == "menu:today":
        today_ar = _today_arabic()
        sessions = db.get_sessions_by_day(today_ar)
        if not sessions:
            await query.edit_message_text(
                f"📅 لا توجد حصص اليوم ({today_ar}).",
                reply_markup=admin_main_menu(),
            )
        else:
            lines = [f"📅 <b>حصص اليوم — {today_ar}</b>\n"]
            for s in sessions:
                st = "✅" if not s["is_cancelled"] else "❌"
                lines.append(f"{st} {s['start_time']}-{s['end_time']} | {s['subject']} | {s['room']}")
            await query.edit_message_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_main_menu(),
            )

    elif data == "menu:all":
        sessions = db.get_all_sessions(include_cancelled=True)
        if not sessions:
            await query.edit_message_text("📭 لا توجد حصص.", reply_markup=admin_main_menu())
        else:
            by_day: dict[str, list] = {}
            for s in sessions:
                by_day.setdefault(s["day"], []).append(s)
            text = "📋 <b>الجدول الكامل</b>\n\n"
            for day, ss in by_day.items():
                text += f"<b>── {day} ──</b>\n"
                for s in ss:
                    icon = "✅" if not s["is_cancelled"] else "❌"
                    text += f"  {icon} {s['start_time']}–{s['end_time']} | {s['subject']} | {s['room']}\n"
                text += "\n"
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

    elif data == "menu:settings":
        from keyboards import settings_menu_keyboard
        trans_topic = db.get_setting("translate_topic_id", "2")
        topic_desc = f"الموضوع رقم {trans_topic}" if trans_topic and trans_topic != "0" else "كافة المواضيع (عام)"
        is_on = db.get_setting("translate_enabled", "1") == "1"
        status_label = "شغالة 🟢" if is_on else "متوقفة ⏸️"

        text = (
            "⚙️ <b>إعدادات الترجمة</b>\n\n"
            f"📌 <b>موضوع الترجمة:</b> <code>{topic_desc}</code>\n"
            f"⚡ <b>حالة الخدمة:</b> <b>{status_label}</b>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=settings_menu_keyboard())

    elif data == "trans:toggle":
        from keyboards import settings_menu_keyboard
        curr = db.get_setting("translate_enabled", "1")
        new_val = "0" if curr == "1" else "1"
        db.set_setting("translate_enabled", new_val)
        status_txt = "🟢 تم تفعيل الترجمة!" if new_val == "1" else "⏸️ تم إيقاف الترجمة!"
        await query.answer(status_txt, show_alert=False)

        trans_topic = db.get_setting("translate_topic_id", "2")
        topic_desc = f"الموضوع رقم {trans_topic}" if trans_topic and trans_topic != "0" else "كافة المواضيع (عام)"
        status_label = "شغالة 🟢" if new_val == "1" else "متوقفة ⏸️"
        text = (
            "⚙️ <b>إعدادات الترجمة</b>\n\n"
            f"📌 <b>موضوع الترجمة:</b> <code>{topic_desc}</code>\n"
            f"⚡ <b>حالة الخدمة:</b> <b>{status_label}</b>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=settings_menu_keyboard())

    elif data == "trans:lockhere":
        from keyboards import settings_menu_keyboard
        target_thread = query.message.message_thread_id
        if target_thread:
            db.set_setting("translate_topic_id", str(target_thread))
            await query.answer(f"✅ تم قفل الترجمة على هذا الموضوع (#{target_thread})!", show_alert=True)
            topic_desc = f"الموضوع رقم {target_thread}"
        else:
            db.set_setting("translate_topic_id", "0")
            await query.answer("🌐 تم تفعيل الترجمة في كل المواضيع (عام)!", show_alert=True)
            topic_desc = "كافة المواضيع (عام)"

        is_on = db.get_setting("translate_enabled", "1") == "1"
        status_label = "شغالة 🟢" if is_on else "متوقفة ⏸️"
        text = (
            "⚙️ <b>إعدادات الترجمة</b>\n\n"
            f"📌 <b>موضوع الترجمة:</b> <code>{topic_desc}</code>\n"
            f"⚡ <b>حالة الخدمة:</b> <b>{status_label}</b>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=settings_menu_keyboard())

    elif data == "trans:setall":
        from keyboards import settings_menu_keyboard
        db.set_setting("translate_topic_id", "0")
        await query.answer("🌐 تم تفعيل الترجمة في كل المواضيع!", show_alert=True)
        is_on = db.get_setting("translate_enabled", "1") == "1"
        status_label = "شغالة 🟢" if is_on else "متوقفة ⏸️"
        text = (
            "⚙️ <b>إعدادات الترجمة</b>\n\n"
            f"📌 <b>موضوع الترجمة:</b> <code>كافة المواضيع (عام)</code>\n"
            f"⚡ <b>حالة الخدمة:</b> <b>{status_label}</b>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=settings_menu_keyboard())

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

    # ── 3. ميزة الترجمة التلقائية ────────────────────────────────
    translate_enabled = db.get_setting("translate_enabled", "1")
    if translate_enabled == "1":
        # في المحادثات الخاصة مع البوت: يترجم دائماً
        is_private = chat and chat.type == "private"

        # في المجموعات: فحص مطابقة رقم الموضوع (Topic)
        if not is_private:
            configured_topic = db.get_setting("translate_topic_id", "0")
            current_thread_id = msg.message_thread_id

            # إذا حُدد موضوع معين (وليس 0 للكل) ولم تتطابق الرسالة معه، نتجاهلها
            if configured_topic and configured_topic != "0":
                try:
                    target_thread_id = int(configured_topic)
                except ValueError:
                    target_thread_id = None
                if target_thread_id is not None and current_thread_id != target_thread_id:
                    return

        # التحقق من احتواء النص على حروف عربية
        import re
        if not re.search(r"[\u0600-\u06FF]", text):
            return

        # ترجمة النص إلى الإنجليزية
        translated = translate_ar_to_en(text)
        if not translated or translated.strip().lower() == text.strip().lower():
            # إذا تعذرت الترجمة أو لم يتغير النص، لا نكرر النص العربي في الشات
            return

        reply_text = f"🇬🇧 {translated}"

        try:
            await msg.reply_text(
                reply_text,
                disable_web_page_preview=True,
            )
            logger.info(f"✅ تمت الترجمة بنجاح ({text} -> {translated}) للمستخدم {user.id if user else 0}")
        except Exception as e:
            logger.error(f"❌ خطأ أثناء إرسال رد الترجمة: {e}")


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
    """أرجع اسم اليوم الحالي بالعربية."""
    weekday_map = {
        0: "الاثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد",
    }
    return weekday_map[datetime.now().weekday()]


def _tomorrow_arabic() -> str:
    """أرجع اسم يوم الغد بالعربية."""
    from datetime import timedelta
    weekday_map = {
        0: "الاثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد",
    }
    tomorrow = datetime.now() + timedelta(days=1)
    return weekday_map[tomorrow.weekday()]


# ══════════════════════════════════════════════════════════════
#  أوامر متقدمة إضافية (Next, Tomorrow, Topics, Control)
# ══════════════════════════════════════════════════════════════

async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معرفة الحصة القادمة مباشرة بناءً على التوقيت الحالي."""
    now = datetime.now()
    today_ar = _today_arabic()
    sessions = db.get_sessions_by_day(today_ar)
    current_time_str = now.strftime("%H:%M")

    current_running = None
    upcoming = []

    for s in sessions:
        if s["start_time"] <= current_time_str <= s["end_time"]:
            current_running = s
        elif s["start_time"] > current_time_str:
            upcoming.append(s)

    parts = []
    if current_running:
        parts.append(
            f"🟢 <b>حصة جارية الآن:</b>\n"
            f"📚 <b>{current_running['subject']}</b>\n"
            f"⏰ <code>{current_running['start_time']}</code> ➔ <code>{current_running['end_time']}</code>\n"
            f"📍 {current_running['room']}"
        )

    if upcoming:
        next_s = upcoming[0]
        try:
            h, m = map(int, next_s["start_time"].split(":"))
            target_dt = now.replace(hour=h, minute=m, second=0)
            diff_mins = int((target_dt - now).total_seconds() / 60)
            if diff_mins <= 0:
                diff_text = "تبدأ الآن"
            elif diff_mins < 60:
                diff_text = f"بعد {diff_mins} دقيقة"
            else:
                diff_text = f"بعد {diff_mins // 60} ساعة و {diff_mins % 60} دقيقة"
        except Exception:
            diff_text = ""

        parts.append(
            f"⏳ <b>الحصة القادمة ({diff_text}):</b>\n"
            f"📚 <b>{next_s['subject']}</b>\n"
            f"⏰ <code>{next_s['start_time']}</code> ➔ <code>{next_s['end_time']}</code>\n"
            f"📍 {next_s['room']}"
        )
    elif not current_running:
        tomorrow_ar = _tomorrow_arabic()
        tomorrow_sessions = db.get_sessions_by_day(tomorrow_ar)
        if tomorrow_sessions:
            first_s = tomorrow_sessions[0]
            parts.append(
                f"✨ انتهت جميع حصص اليوم (<b>{today_ar}</b>)!\n\n"
                f"🌅 <b>أول حصة غداً ({tomorrow_ar}):</b>\n"
                f"📚 <b>{first_s['subject']}</b>\n"
                f"⏰ <code>{first_s['start_time']}</code> ➔ <code>{first_s['end_time']}</code>\n"
                f"📍 {first_s['room']}"
            )
        else:
            parts.append(f"✨ انتهت جميع حصص اليوم (<b>{today_ar}</b>) ولا توجد حصص مجدولة غداً (<b>{tomorrow_ar}</b>).")

    await update.effective_message.reply_text("\n\n".join(parts), parse_mode=ParseMode.HTML)


async def cmd_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جدول الغد."""
    tomorrow_ar = _tomorrow_arabic()
    sessions = db.get_sessions_by_day(tomorrow_ar)

    if not sessions:
        await update.effective_message.reply_text(f"🏖️ لا توجد حصص دراسية غداً (<b>{tomorrow_ar}</b>).", parse_mode=ParseMode.HTML)
        return

    lines = [f"🌅 <b>جدول الغد — {tomorrow_ar}</b>\n"]
    for s in sessions:
        lines.append(
            f"• <b>{s['subject']}</b>\n"
            f"  ⏰ <code>{s['start_time']}</code> ➔ <code>{s['end_time']}</code>  |  📍 <b>{s['room']}</b>\n"
        )
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


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
    """عرض إعدادات الترجمة والمواضيع بشكل مبسط وسريع."""
    if not await _check_admin(update):
        return

    trans_topic = db.get_setting("translate_topic_id", "2")
    topic_desc = f"الموضوع رقم {trans_topic}" if trans_topic and trans_topic != "0" else "كافة المواضيع (عام)"
    is_on = db.get_setting("translate_enabled", "1") == "1"
    status_label = "شغالة 🟢" if is_on else "متوقفة ⏸️"

    schedule_topic = db.get_setting("topic_id", "4")
    schedule_status = "مفعّلة 🟢" if db.get_setting("alerts_enabled", "1") == "1" else "معطلة ⏸️"

    text = (
        "⚙️ <b>لوحة الإعدادات المبسطة</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 <b>إعدادات الترجمة:</b>\n"
        f"• موضوع الترجمة: <b>{topic_desc}</b>\n"
        f"• حالة الخدمة: <b>{status_label}</b>\n"
        "  └ التبديل: <code>/translatemode on|off</code>\n"
        "  └ تغيير التوبك: <code>/translatetopic [رقم]</code>\n\n"
        "📅 <b>تنبيهات الجدول الدراسي:</b>\n"
        f"• موضوع التنبيهات: <b>الموضوع رقم {schedule_topic}</b>\n"
        f"• حالة التنبيهات: <b>{schedule_status}</b>\n"
        "  └ تغيير التوبك: <code>/settopic [رقم]</code>\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)



