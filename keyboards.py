"""
keyboards.py - لوحات المفاتيح التفاعلية (Inline Keyboards)
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import CC_ROOMS, NORMAL_ROOMS, AMPHI_ROOMS, ALL_ROOMS


# ══════════════════════════════════════════════════════════════
#  لوحة القائمة الرئيسية للمشرف
# ══════════════════════════════════════════════════════════════

def admin_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 عرض الجدول اليوم",   callback_data="menu:today")],
        [InlineKeyboardButton("📅 عرض كل الجدول",      callback_data="menu:all")],
        [InlineKeyboardButton("✏️ تعديل حصة",          callback_data="menu:edit")],
        [InlineKeyboardButton("❌ إلغاء حصة",           callback_data="menu:cancel")],
        [InlineKeyboardButton("♻️ استعادة حصة",        callback_data="menu:restore")],
        [InlineKeyboardButton("🗑️ حذف حصة نهائياً",   callback_data="menu:delete")],
        [InlineKeyboardButton("👤 إدارة المشرفين",     callback_data="menu:admins")],
        [InlineKeyboardButton("⚙️ إعدادات الترجمة والمواضيع", callback_data="menu:settings")],
        [InlineKeyboardButton("📤 رفع PDF جديد",       callback_data="menu:upload")],
    ])


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    """لوحة الإعدادات الرئيسية التي تتضمن إعدادات توبيك الترجمة وإعدادات توبيك الحصص."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 إعدادات توبيك الترجمة", callback_data="settings:translate")],
        [InlineKeyboardButton("📅 إعدادات توبيك إرسال الحصص", callback_data="settings:schedule")],
        [InlineKeyboardButton("✨ إعدادات Google Gemini AI", callback_data="settings:gemini")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="menu:back")],
    ])


def translate_settings_keyboard(current_lang: str | None = None) -> InlineKeyboardMarkup:
    """لوحة التحكم الخاصة بتوبيك الترجمة وخيارات اللغات (عربي / إنجليزي)."""
    if current_lang is None:
        try:
            import database as db
            current_lang = db.get_setting("translate_target_lang", "auto")
        except Exception:
            current_lang = "auto"

    btn_en = f"🇬🇧 إنجليزي {'✅' if current_lang == 'en' else ''}"
    btn_ar = f"🇸🇦 عربي {'✅' if current_lang == 'ar' else ''}"
    btn_auto = f"🔄 ثنائي (عربي ↔️ EN) {'✅' if current_lang == 'auto' else ''}"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تشغيل / إيقاف الترجمة", callback_data="trans:toggle")],
        [
            InlineKeyboardButton(btn_en, callback_data="trans:lang:en"),
            InlineKeyboardButton(btn_ar, callback_data="trans:lang:ar"),
        ],
        [InlineKeyboardButton(btn_auto, callback_data="trans:lang:auto")],
        [InlineKeyboardButton("📌 قفل الترجمة على هذا التوبك", callback_data="trans:lockhere")],
        [InlineKeyboardButton("🌐 تفعيل في كل التوبكات (عام)", callback_data="trans:setall")],
        [InlineKeyboardButton("✏️ إدخال رقم توبك الترجمة يدوياً", callback_data="trans:custom_id")],
        [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="menu:settings")],
    ])


def schedule_topic_settings_keyboard() -> InlineKeyboardMarkup:
    """لوحة التحكم الخاصة بتوبيك إرسال الحصص والتنبيهات."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 تشغيل / إيقاف تنبيهات الحصص", callback_data="sched:toggle_alerts")],
        [InlineKeyboardButton("📌 قفل إرسال الحصص على هذا التوبك", callback_data="sched:lockhere")],
        [InlineKeyboardButton("✏️ إدخال رقم توبك الحصص يدوياً", callback_data="sched:custom_id")],
        [InlineKeyboardButton("🚨 إرسال تنبيه تجريبي هنا", callback_data="sched:test_alert")],
        [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="menu:settings")],
    ])


def gemini_settings_keyboard() -> InlineKeyboardMarkup:
    """لوحة التحكم الخاصة بمفتاح Google Gemini API."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 إدخال / تحديث مفتاح Gemini API", callback_data="gemini:set_key")],
        [InlineKeyboardButton("🧪 فحص وتجربة الترجمة بـ Gemini", callback_data="gemini:test")],
        [InlineKeyboardButton("🗑️ حذف المفتاح (استخدام المحرك البديل)", callback_data="gemini:clear_key")],
        [InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="menu:settings")],
    ])


# ══════════════════════════════════════════════════════════════
#  لوحة اختيار الحصة للتعديل
# ══════════════════════════════════════════════════════════════

def sessions_keyboard(sessions: list, action: str) -> InlineKeyboardMarkup:
    """أنشئ لوحة بأزرار الحصص لتنفيذ إجراء معيّن (edit/cancel/restore/delete)."""
    buttons = []
    for s in sessions:
        label = f"{'✅' if not s['is_cancelled'] else '❌'} {s['day']} {s['start_time']} | {s['subject']}"
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"{action}:session:{s['id']}")
        ])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")])
    return InlineKeyboardMarkup(buttons)


# ══════════════════════════════════════════════════════════════
#  لوحة اختيار نوع التعديل على الحصة
# ══════════════════════════════════════════════════════════════

def edit_options_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏫 تغيير القاعة",   callback_data=f"edit:room:{session_id}")],
        [InlineKeyboardButton("⏰ تغيير الوقت",   callback_data=f"edit:time:{session_id}")],
        [InlineKeyboardButton("📝 تغيير المادة",  callback_data=f"edit:subject:{session_id}")],
        [InlineKeyboardButton("🔙 رجوع",          callback_data="menu:edit")],
    ])


# ══════════════════════════════════════════════════════════════
#  لوحة اختيار نوع الغرفة
# ══════════════════════════════════════════════════════════════

def room_type_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖥️ غرف CC (1-6)",       callback_data=f"room:cc:{session_id}")],
        [InlineKeyboardButton("🏫 غرف عادية (1-18)",   callback_data=f"room:normal:{session_id}")],
        [InlineKeyboardButton("🏛️ مدرجات Amphi (1-5)",  callback_data=f"room:amphi:{session_id}")],
        [InlineKeyboardButton("🔙 رجوع",              callback_data=f"edit:room:{session_id}")],
    ])


def amphi_rooms_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """لوحة اختيار مدرج Amphi."""
    buttons = []
    row = []
    for room in AMPHI_ROOMS:
        row.append(InlineKeyboardButton(room, callback_data=f"setroom:{session_id}:{room}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"room:type:{session_id}")])
    return InlineKeyboardMarkup(buttons)


def cc_rooms_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """لوحة اختيار غرفة CC."""
    buttons = []
    row = []
    for i, room in enumerate(CC_ROOMS):
        row.append(InlineKeyboardButton(room, callback_data=f"setroom:{session_id}:{room}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"room:type:{session_id}")])
    return InlineKeyboardMarkup(buttons)


def normal_rooms_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """لوحة اختيار غرفة عادية."""
    buttons = []
    row = []
    for i, room in enumerate(NORMAL_ROOMS):
        row.append(InlineKeyboardButton(room, callback_data=f"setroom:{session_id}:{room}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"room:type:{session_id}")])
    return InlineKeyboardMarkup(buttons)


# ══════════════════════════════════════════════════════════════
#  لوحة تأكيد
# ══════════════════════════════════════════════════════════════

def confirm_keyboard(action: str, target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم، تأكيد",  callback_data=f"confirm:{action}:{target_id}"),
            InlineKeyboardButton("❌ إلغاء",       callback_data="menu:back"),
        ]
    ])


# ══════════════════════════════════════════════════════════════
#  لوحات تصفح الجداول الحديثة (Modern Schedule Browsing)
# ══════════════════════════════════════════════════════════════

SCHEDULE_STUDY_DAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]


def day_schedule_keyboard(current_day: str) -> InlineKeyboardMarkup:
    """أزرار تصفح جدول يوم معين مع تمييز اليوم الحالي والتنقل السريع."""
    day_row1 = []
    day_row2 = []
    for i, day in enumerate(SCHEDULE_STUDY_DAYS):
        label = f"📍 {day}" if day == current_day else day
        cb_data = f"view_day:{day}"
        if i < 3:
            day_row1.append(InlineKeyboardButton(label, callback_data=cb_data))
        else:
            day_row2.append(InlineKeyboardButton(label, callback_data=cb_data))

    action_row = [
        InlineKeyboardButton("🔄 تحديث", callback_data=f"view_day:{current_day}"),
        InlineKeyboardButton("🌅 الغد", callback_data="btn:tomorrow"),
        InlineKeyboardButton("📋 الأسبوع", callback_data="btn:week"),
    ]
    quick_row = [
        InlineKeyboardButton("⏭️ الحصة القادمة", callback_data="btn:next"),
        InlineKeyboardButton("📅 جدول اليوم", callback_data="btn:today"),
    ]
    return InlineKeyboardMarkup([day_row1, day_row2, action_row, quick_row])


def week_overview_keyboard() -> InlineKeyboardMarkup:
    """أزرار لوحة التحكم الأسبوعية لفتح تفاصيل أي يوم."""
    day_row1 = [
        InlineKeyboardButton("الأحد", callback_data="view_day:الأحد"),
        InlineKeyboardButton("الاثنين", callback_data="view_day:الاثنين"),
        InlineKeyboardButton("الثلاثاء", callback_data="view_day:الثلاثاء"),
    ]
    day_row2 = [
        InlineKeyboardButton("الأربعاء", callback_data="view_day:الأربعاء"),
        InlineKeyboardButton("الخميس", callback_data="view_day:الخميس"),
    ]
    action_row = [
        InlineKeyboardButton("📅 جدول اليوم", callback_data="btn:today"),
        InlineKeyboardButton("⏭️ الحصة القادمة", callback_data="btn:next"),
    ]
    return InlineKeyboardMarkup([day_row1, day_row2, action_row])


def next_session_keyboard() -> InlineKeyboardMarkup:
    """أزرار بطاقة الحصة القادمة والجارية."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 جدول اليوم", callback_data="btn:today"),
            InlineKeyboardButton("🌅 جدول الغد", callback_data="btn:tomorrow"),
        ],
        [
            InlineKeyboardButton("📋 ملخص الأسبوع", callback_data="btn:week"),
            InlineKeyboardButton("🔄 تحديث الوقت", callback_data="btn:next"),
        ]
    ])

