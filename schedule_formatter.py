"""
schedule_formatter.py - منسّق الجداول وبطاقات العرض التفاعلية لبوت تيليجرام
يمنح البوت مظهراً حديثاً، بطاقات منظمة، ومؤشرات ذكية للحصص الجارية والقادمة.
"""
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from config import TIMEZONE

DAYS_ORDER = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"]

# قائمة الأيام الدراسية الفعلية
STUDY_DAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]


def get_current_datetime() -> datetime:
    """الحصول على التاريخ والوقت الحالي وفق المنطقة الزمنية المحددة في الإعدادات."""
    try:
        return datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        return datetime.now()


def get_today_name() -> str:
    """أرجع اسم اليوم الحالي بالعربية وفق التوقيت المحلي."""
    now = get_current_datetime()
    weekday_map = {
        0: "الاثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد",
    }
    return weekday_map[now.weekday()]


def get_tomorrow_name() -> str:
    """أرجع اسم يوم الغد بالعربية وفق التوقيت المحلي."""
    now = get_current_datetime()
    tomorrow = now + timedelta(days=1)
    weekday_map = {
        0: "الاثنين",
        1: "الثلاثاء",
        2: "الأربعاء",
        3: "الخميس",
        4: "الجمعة",
        5: "السبت",
        6: "الأحد",
    }
    return weekday_map[tomorrow.weekday()]


def parse_session_details(raw_subject: str, room: str) -> dict:
    """
    تحليل نص المادة والقاعة لاستخراج:
    - العنوان النظيف
    - اسم الأستاذ
    - نوع الحصة (محاضرة / أعمال موجهة / أعمال تطبيقية)
    - الفوج (Group 1 / Group 2)
    - نوع القاعة ورمزها
    """
    subject = raw_subject.strip()
    session_type = "📚 حصة دراسية"
    session_badge = "حصة"
    type_icon = "📚"
    group = None
    teacher = None

    # كشف الفوج
    if "group 1" in subject.lower() or "sgr1" in subject.lower():
        group = "الفوج 1 (G1)"
    elif "group 2" in subject.lower() or "sgr2" in subject.lower():
        group = "الفوج 2 (G2)"

    # كشف نوع الحصة
    subj_upper = subject.upper()
    if "PW" in subj_upper or "TP" in subj_upper:
        session_type = "🔬 مخبر / أعمال تطبيقية (TP/PW)"
        session_badge = "مخبر TP"
        type_icon = "🔬"
    elif "TU" in subj_upper or "TD" in subj_upper or " TUTORIAL" in subj_upper:
        session_type = "✏️ أعمال موجهة (TD/Tu)"
        session_badge = "أعمال موجهة TD"
        type_icon = "✏️"
    elif "COURSE" in subj_upper or "COURS" in subj_upper:
        session_type = "📖 محاضرة (Course)"
        session_badge = "محاضرة"
        type_icon = "📖"

    # كشف نوع القاعة
    room_clean = room.strip()
    room_upper = room_clean.upper()
    if room_upper.startswith("CC"):
        room_icon = "🖥️"
        room_desc = f"مخبر حاسوب ({room_clean})"
    elif room_upper.startswith("AMPHI"):
        room_icon = "🏛️"
        room_desc = f"مدرج محاضرات ({room_clean})"
    elif room_upper.startswith("ROOM"):
        room_icon = "🏫"
        room_desc = f"قاعة دراسية ({room_clean})"
    else:
        room_icon = "📍"
        room_desc = room_clean

    return {
        "title": subject,
        "type": session_type,
        "badge": session_badge,
        "type_icon": type_icon,
        "group": group,
        "room_clean": room_clean,
        "room_icon": room_icon,
        "room_desc": room_desc,
    }


def _calc_time_diff_mins(target_time_str: str, base_dt: datetime) -> int:
    """حساب فارق الدقائق بين وقت HH:MM والوقت الحالي اليوم."""
    try:
        h, m = map(int, target_time_str.split(":"))
        target_dt = base_dt.replace(hour=h, minute=m, second=0, microsecond=0)
        return int((target_dt - base_dt).total_seconds() / 60)
    except Exception:
        return 0


def format_day_schedule(day: str, sessions: list, is_today: bool = False) -> str:
    """
    تنسيق جدول يوم معين في بطاقة جميلة واحترافية متوافقة مع Telegram HTML.
    """
    now = get_current_datetime()
    curr_time_str = now.strftime("%H:%M")

    header_icon = "📅" if is_today else "🗓️"
    title_suffix = " — اليوم" if is_today else ""

    text = f"{header_icon} <b>جدول يوم {day}{title_suffix}</b>\n"
    if is_today:
        text += f"⏰ <b>الوقت الحالي:</b> <code>{curr_time_str}</code>\n"
    text += f"📊 <b>إجمالي الحصص:</b> <b>{len(sessions)} حصص</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if not sessions:
        text += f"🏖️ <b>عطلة! لا توجد حصص مجدولة ليوم {day}.</b>\n\n"
        text += "استغل اليوم في المراجعة والاستراحة! ✨\n"
        return text

    active_count = 0
    upcoming_count = 0

    for i, s in enumerate(sessions, 1):
        details = parse_session_details(s["subject"], s["room"])
        st = s["start_time"]
        et = s["end_time"]
        is_cancelled = bool(s["is_cancelled"])

        # تحديد الحالة بالنسبة لليوم الحالي
        status_line = ""
        border_icon = "🔹"

        if is_cancelled:
            border_icon = "❌"
            status_line = "  ⚠️ <i>(ملغاة)</i>"
        elif is_today:
            if st <= curr_time_str <= et:
                # الحصة جارية الآن
                active_count += 1
                rem_mins = _calc_time_diff_mins(et, now)
                border_icon = "🟢"
                status_line = f"  <tg-spoiler><b>[جارية الآن • متبقي {rem_mins} د]</b></tg-spoiler>"
            elif curr_time_str < st:
                # الحصة قادمة
                upcoming_count += 1
                diff_mins = _calc_time_diff_mins(st, now)
                if diff_mins < 60:
                    time_hint = f"بعد {diff_mins} دقيقة"
                else:
                    time_hint = f"بعد {diff_mins // 60} س و {diff_mins % 60} د"
                border_icon = "⏳"
                status_line = f"  <i>(تبدأ {time_hint})</i>"
            else:
                # الحصة انتهت
                border_icon = "⚪"
                status_line = "  <i>(انتهت)</i>"

        # تنسيق الحصة كفقرة كارت واضحة
        group_badge = f"  [<code>{details['group']}</code>]" if details["group"] else ""
        text += f"{border_icon} <b>{i}. {details['type_icon']} {details['title']}</b>{group_badge}\n"
        text += f"   ⏰ <code>{st}</code> ➔ <code>{et}</code>{status_line}\n"
        text += f"   {details['room_icon']} <b>{details['room_clean']}</b>  <i>({details['badge']})</i>\n"
        text += "────────────────────\n"

    # التذييل الذكي
    if is_today:
        text += "\n"
        if active_count > 0:
            text += "🟢 <b>تنبيه:</b> هناك حصة دراسية جارية الآن!\n"
        elif upcoming_count > 0:
            text += f"⏳ <b>متبقي اليوم:</b> {upcoming_count} حصة قادمة.\n"
        else:
            text += "✨ <b>انتهت جميع حصص اليوم بنجاح! أحسنتم!</b> 🎉\n"

    return text


def format_week_overview(all_sessions: list) -> str:
    """
    تنسيق ملخص الأسبوع الذكي (Weekly Dashboard) بأناقة بالغة.
    """
    # تجميع الحصص حسب الأيام وفق ترتيب أيام الأسبوع
    by_day: dict[str, list] = {day: [] for day in STUDY_DAYS}
    total_active = 0

    for s in all_sessions:
        if s["day"] in by_day:
            by_day[s["day"]].append(s)
            if not s["is_cancelled"]:
                total_active += 1

    text = "📋 <b>الجدول الأسبوعي الكامل (Semester 1)</b>\n"
    text += f"🏛️ <b>إجمالي الحصص:</b> <b>{total_active} حصة أسبوعياً</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    day_emojis = {
        "الأحد": "1️⃣",
        "الاثنين": "2️⃣",
        "الثلاثاء": "3️⃣",
        "الأربعاء": "4️⃣",
        "الخميس": "5️⃣",
    }

    for day in STUDY_DAYS:
        day_sessions = by_day[day]
        emoji = day_emojis.get(day, "🔹")
        if not day_sessions:
            text += f"{emoji} <b>{day}:</b> 🏖️ <i>عطلة</i>\n\n"
            continue

        first_st = day_sessions[0]["start_time"]
        last_et = day_sessions[-1]["end_time"]
        count = len(day_sessions)

        text += f"{emoji} <b>يوم {day}</b>  (<code>{count} حصص</code>)\n"
        text += f"   ⏱️ من <code>{first_st}</code> إلى <code>{last_et}</code>\n"

        # ملخص عناوين المواد
        subj_previews = []
        for s in day_sessions:
            d = parse_session_details(s["subject"], s["room"])
            status = "❌ " if s["is_cancelled"] else ""
            subj_previews.append(f"• {status}{d['type_icon']} <code>{s['start_time']}</code> {s['subject'][:28]}")

        text += "\n".join(f"   {p}" for p in subj_previews)
        text += "\n\n"

    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "💡 <b>تصفح الأيام:</b> اضغط على أي يوم أدناه لعرض بطاقة تفاصيله الكاملة مباشرة."
    return text


def format_next_card(current_running: Optional[dict], upcoming: list, tomorrow_first: Optional[dict], today_ar: str) -> str:
    """
    تنسيق بطاقة الحصة القادمة والجارية (/next) بشكل بطاقة تفاعلية فائقة الجمال.
    """
    now = get_current_datetime()
    curr_time_str = now.strftime("%H:%M")

    parts = []

    if current_running:
        d = parse_session_details(current_running["subject"], current_running["room"])
        rem_mins = _calc_time_diff_mins(current_running["end_time"], now)
        # شريط تقدم افتراضي
        total_dur = _calc_time_diff_mins(current_running["end_time"], now.replace(
            hour=int(current_running["start_time"].split(":")[0]),
            minute=int(current_running["start_time"].split(":")[1])
        ))
        progress_blocks = "🟩" * 3 + "⬜" * 2

        parts.append(
            f"🟢 <b>حصة جارية الآن</b> {progress_blocks}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{d['type_icon']} <b>المادة:</b> <b>{current_running['subject']}</b>\n"
            f"⏰ <b>الوقت:</b> <code>{current_running['start_time']}</code> ➔ <code>{current_running['end_time']}</code>\n"
            f"{d['room_icon']} <b>المكان:</b> <b>{d['room_clean']}</b>  <i>({d['room_desc']})</i>\n"
            f"⏳ <b>متبقي على الانتهاء:</b> <b>{rem_mins} دقيقة</b>"
        )

    if upcoming:
        next_s = upcoming[0]
        d = parse_session_details(next_s["subject"], next_s["room"])
        diff_mins = _calc_time_diff_mins(next_s["start_time"], now)
        if diff_mins <= 0:
            diff_text = "تبدأ في هذه اللحظة!"
        elif diff_mins < 60:
            diff_text = f"بعد <b>{diff_mins} دقيقة</b>"
        else:
            diff_text = f"بعد <b>{diff_mins // 60} ساعة و {diff_mins % 60} دقيقة</b>"

        parts.append(
            f"⏳ <b>الحصة القادمة ({diff_text}):</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{d['type_icon']} <b>المادة:</b> <b>{next_s['subject']}</b>\n"
            f"⏰ <b>الوقت:</b> <code>{next_s['start_time']}</code> ➔ <code>{next_s['end_time']}</code>\n"
            f"{d['room_icon']} <b>المكان:</b> <b>{d['room_clean']}</b>  <i>({d['room_desc']})</i>\n"
            f"📌 <b>النوع:</b> {d['type']}"
        )
    elif not current_running:
        if tomorrow_first:
            d = parse_session_details(tomorrow_first["subject"], tomorrow_first["room"])
            parts.append(
                f"✨ <b>انتهت جميع حصص اليوم ({today_ar})!</b> 🎉\n\n"
                f"🌅 <b>أول حصة غداً:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{d['type_icon']} <b>المادة:</b> <b>{tomorrow_first['subject']}</b>\n"
                f"⏰ <b>الوقت:</b> <code>{tomorrow_first['start_time']}</code> ➔ <code>{tomorrow_first['end_time']}</code>\n"
                f"{d['room_icon']} <b>المكان:</b> <b>{d['room_clean']}</b>\n\n"
                f"تمنياتنا لكم بأمسية ممتعة ومريحة! 🌙"
            )
        else:
            parts.append(
                f"✨ <b>انتهت حصص اليوم ({today_ar})!</b>\n"
                f"🏖️ لا توجد حصص مجدولة ليوم الغد. استمتعوا بالعطلة! 🌟"
            )

    return "\n\n".join(parts)
