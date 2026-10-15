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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تشغيل / إيقاف", callback_data="trans:toggle")],
        [InlineKeyboardButton("📌 قفل على هذا التوبك", callback_data="trans:lockhere")],
        [InlineKeyboardButton("🌐 تفعيل في كل التوبكات", callback_data="trans:setall")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu:back")],
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
