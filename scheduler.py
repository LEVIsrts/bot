"""
scheduler.py - جدولة التنبيهات قبل بداية كل حصة
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.constants import ParseMode

import database as db
from config import GROUP_CHAT_ID, REMINDER_MINUTES_BEFORE, TOPIC_ID, TIMEZONE

logger = logging.getLogger(__name__)

# خريطة اليوم العربي → نص اليوم الإنجليزي الصريح (تجنباً لأي التباس)
DAY_OF_WEEK: dict[str, str] = {
    "الأحد":     "sun",
    "الاثنين":   "mon",
    "الثلاثاء":  "tue",
    "الأربعاء":  "wed",
    "الخميس":    "thu",
    "الجمعة":    "fri",
    "السبت":     "sat",
}


# ══════════════════════════════════════════════════════════════
#  إنشاء المجدول
# ══════════════════════════════════════════════════════════════

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    return scheduler


# ══════════════════════════════════════════════════════════════
#  بناء رسالة التنبيه
# ══════════════════════════════════════════════════════════════

async def _build_mention_text(bot: Bot) -> str:
    """بنِ نص المنشن لجميع الأعضاء المسجلين."""
    members = db.get_all_members()
    if not members:
        return "@everyone"

    mentions: list[str] = []
    for m in members:
        if m["username"]:
            mentions.append(f"@{m['username']}")
        else:
            # منشن بدون username بالاسم الكامل
            mentions.append(
                f"<a href='tg://user?id={m['user_id']}'>{m['full_name']}</a>"
            )
    return " ".join(mentions)


from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_target_chat_and_topic() -> tuple[int, Optional[int]]:
    """الحصول على معرّف المجموعة والتوبك (مع إمكانية التعديل الديناميكي من DB)."""
    chat_id_str = db.get_setting("group_chat_id")
    chat_id = int(chat_id_str) if chat_id_str else GROUP_CHAT_ID

    topic_id_str = db.get_setting("topic_id")
    if topic_id_str is not None:
        topic_id = int(topic_id_str) if topic_id_str not in ("0", "") else None
    else:
        topic_id = TOPIC_ID
    return chat_id, topic_id


async def send_alert(bot: Bot, session_id: int) -> None:
    """أرسل تنبيه الحصة إلى الموضوع (Topic) في المجموعة مع تصميم احترافي."""
    # التحقق من حالة التنبيهات
    if db.get_setting("alerts_enabled", "1") == "0":
        logger.info(f"⏸️ التنبيهات معطلة مؤقتاً، تم تخطي الحصة {session_id}.")
        return

    session = db.get_session(session_id)
    if not session:
        logger.warning(f"⚠️ الحصة {session_id} غير موجودة عند إرسال التنبيه.")
        return

    if session["is_cancelled"]:
        logger.info(f"ℹ️ الحصة {session_id} ملغاة، لا يُرسَل تنبيه.")
        return

    # استخراج تفاصيل منسقة وذكية للحصة
    from schedule_formatter import parse_session_details
    d = parse_session_details(session["subject"], session["room"])

    mention_text = await _build_mention_text(bot)

    text = (
        f"🚨 <b>تنبيه باقتراب موعد الحصة الدراسية</b> 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ <b>تبدأ بعد:</b> <code>{REMINDER_MINUTES_BEFORE} دقيقة</code>\n\n"
        f"{d['type_icon']} <b>المادة:</b> <b>{session['subject']}</b>\n"
        f"📅 <b>اليوم:</b> <b>{session['day']}</b>\n"
        f"⏰ <b>التوقيت:</b> <code>{session['start_time']}</code> ➔ <code>{session['end_time']}</code>\n"
        f"{d['room_icon']} <b>المكان:</b> <b>{d['room_clean']}</b>  <i>({d['room_desc']})</i>\n"
        f"📌 <b>النوع:</b> {d['type']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 {mention_text}"
    )

    # أزرار تفاعلية سريعة أسفل التنبيه
    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 جدول اليوم", callback_data="btn:today"),
            InlineKeyboardButton("⏭️ الحصة التالية", callback_data="btn:next"),
        ],
        [
            InlineKeyboardButton("📋 ملخص الأسبوع", callback_data="btn:week"),
            InlineKeyboardButton("🔄 تغيير القاعة", callback_data=f"edit:room:{session_id}")
        ]
    ])

    chat_id, topic_id = get_target_chat_and_topic()

    send_kwargs = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": ParseMode.HTML,
        "reply_markup": reply_markup,
    }
    if topic_id:
        send_kwargs["message_thread_id"] = topic_id

    try:
        await bot.send_message(**send_kwargs)
        db.log_alert(session_id, "sent")
        logger.info(f"✅ تنبيه الحصة {session_id} أُرسل بنجاح إلى chat_id={chat_id}, topic_id={topic_id}.")
    except Exception as e:
        logger.error(f"❌ فشل إرسال تنبيه الحصة {session_id} إلى التوبك {topic_id}: {e}")
        # خطة احتياطية: إذا فشل الإرسال داخل التوبك (مثلاً معرّف التوبك غير صحيح أو مغلق)، نرسل في المجموعة العامة
        if topic_id:
            try:
                fallback_kwargs = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": ParseMode.HTML,
                    "reply_markup": reply_markup,
                }
                await bot.send_message(**fallback_kwargs)
                db.log_alert(session_id, "sent_fallback_general")
                logger.warning(f"⚠️ تم إرسال تنبيه الحصة {session_id} في المجموعة العامة كبديل للتوبك.")
                return
            except Exception as e_fallback:
                logger.error(f"❌ فشل الإرسال الاحتياطي أيضاً: {e_fallback}")
        db.log_alert(session_id, f"failed: {e}")


# ══════════════════════════════════════════════════════════════
#  إضافة / حذف مهام الجدولة
# ══════════════════════════════════════════════════════════════

def schedule_session_alert(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    session_id: int,
    day: str,
    start_time: str,
) -> Optional[str]:
    """
    جدِّل تنبيهاً أسبوعياً قبل `REMINDER_MINUTES_BEFORE` دقيقة من وقت البداية.
    يعيد job_id إذا نجح، وإلا None.
    """
    dow = DAY_OF_WEEK.get(day)
    if dow is None:
        logger.error(f"❌ يوم غير معروف: {day}")
        return None

    try:
        h, m = map(int, start_time.split(":"))
    except ValueError:
        logger.error(f"❌ توقيت غير صحيح: {start_time}")
        return None

    # حساب وقت التنبيه بدقة
    total_mins = h * 60 + m - REMINDER_MINUTES_BEFORE
    if total_mins < 0:
        total_mins += 24 * 60
    alert_hour = total_mins // 60
    alert_minute = total_mins % 60

    job_id = f"session_{session_id}"

    # أزل المهمة القديمة إن وُجدت
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    trigger = CronTrigger(
        day_of_week=dow,
        hour=alert_hour,
        minute=alert_minute,
        timezone=TIMEZONE,
    )

    job = scheduler.add_job(
        send_alert,
        trigger=trigger,
        args=[bot, session_id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300,
    )

    db.set_session_schedule_id(session_id, job_id)
    next_fire = job.next_run_time
    logger.info(
        f"📅 جُدول تنبيه الحصة {session_id} ({day} {start_time}) "
        f"في {alert_hour:02d}:{alert_minute:02d} [{TIMEZONE}] | الموعد القادم: {next_fire}"
    )
    return job_id


def unschedule_session(scheduler: AsyncIOScheduler, session_id: int) -> None:
    """احذف مهمة التنبيه لحصة معيّنة."""
    job_id = f"session_{session_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"🗑️ حُذف تنبيه الحصة {session_id}.")


def reschedule_all(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """أعِد جدولة تنبيهات كل الحصص النشطة (تُستخدم عند بدء التشغيل أو بعد رفع PDF)."""
    sessions = db.get_all_sessions(include_cancelled=False)
    if not sessions:
        logger.warning("⚠️ تحذير: لا توجد أي حصص في قاعدة البيانات! لن يتم إرسال أي تنبيه.")
        return

    for s in sessions:
        schedule_session_alert(
            scheduler, bot, s["id"], s["day"], s["start_time"]
        )
    logger.info(f"🔄 أُعيدت جدولة {len(sessions)} حصة بنجاح (المنطقة الزمنية: {TIMEZONE}).")
