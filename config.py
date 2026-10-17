"""
config.py - إعدادات البوت المركزية
"""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── معلومات البوت ──────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── قاعدة البيانات ─────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "schedule.db")

# ── معرّفات المشرفين (Admin Telegram IDs) ─────────────────────────────────────
# أضف معرّفاتك هنا أو في ملف .env  ADMIN_IDS=123456789,987654321
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = (
    [int(x.strip()) for x in _raw_admins.split(",") if x.strip()]
    if _raw_admins
    else []
)

# ── معرّف المجموعة التي تُرسَل إليها التنبيهات ─────────────────────────────────
# احصل عليه بإضافة @userinfobot للمجموعة ثم إرسال أي رسالة
GROUP_CHAT_ID: int = int(os.getenv("GROUP_CHAT_ID", "-1004315124879"))

# ── معرّف الموضوع / التوبك (Topic / Thread ID) ──────────────────────────────
# إذا كانت المجموعة تحتوي على مواضيع (Topics/Threads)، حدد رقمه هنا (مثال: 4)
_raw_topic = os.getenv("TOPIC_ID", "4")
TOPIC_ID: int | None = int(_raw_topic) if _raw_topic and _raw_topic.strip() not in ("0", "") else None

# ── المنطقة الزمنية ──────────────────────────────────────────────────────────
# الجزائر: Africa/Algiers  |  السعودية: Asia/Riyadh  |  مصر: Africa/Cairo
TIMEZONE: str = os.getenv("TIMEZONE", "Africa/Algiers")

# ── دقائق التحذير قبل بداية الحصة ────────────────────────────────────────────
REMINDER_MINUTES_BEFORE: int = int(os.getenv("REMINDER_MINUTES_BEFORE", "15"))

# ── الغرف المتاحة ─────────────────────────────────────────────────────────────
CC_ROOMS: list[str] = [f"CC {i}" for i in range(1, 7)]          # CC 1 … CC 6
NORMAL_ROOMS: list[str] = [f"Room {i}" for i in range(1, 19)]   # Room 1 … Room 18
AMPHI_ROOMS: list[str] = [f"Amphi {i}" for i in range(1, 6)]    # Amphi 1 … Amphi 5
ALL_ROOMS: list[str] = CC_ROOMS + NORMAL_ROOMS + AMPHI_ROOMS

# ── أيام الأسبوع بالعربية والإنجليزية (للتحليل من PDF) ────────────────────────
DAY_MAP: dict[str, str] = {
    # الإنجليزية كاملة ومختصرة
    "sunday": "الأحد",    "sun": "الأحد",   "su": "الأحد",
    "monday": "الاثنين",   "mon": "الاثنين",  "mo": "الاثنين",
    "tuesday": "الثلاثاء",  "tue": "الثلاثاء", "tu": "الثلاثاء",
    "wednesday": "الأربعاء","wed": "الأربعاء","we": "الأربعاء",
    "thursday": "الخميس",  "thu": "الخميس",  "th": "الخميس",
    "friday": "الجمعة",    "fri": "الجمعة",   "fr": "الجمعة",
    "saturday": "السبت",   "sat": "السبت",   "sa": "السبت",
    # الفرنسية
    "dimanche": "الأحد",   "dim": "الأحد",
    "lundi": "الاثنين",    "lun": "الاثنين",
    "mardi": "الثلاثاء",   "mar": "الثلاثاء",
    "mercredi": "الأربعاء","mer": "الأربعاء",
    "jeudi": "الخميس",    "jeu": "الخميس",
    "vendredi": "الجمعة", "ven": "الجمعة",
    "samedi": "السبت",    "sam": "السبت",
    # العربية
    "الأحد": "الأحد",   "احد": "الأحد",
    "الاثنين": "الاثنين", "اثنين": "الاثنين",
    "الثلاثاء": "الثلاثاء", "ثلاثاء": "الثلاثاء",
    "الأربعاء": "الأربعاء", "اربعاء": "الأربعاء",
    "الخميس": "الخميس", "خميس": "الخميس",
    "الجمعة": "الجمعة", "جمعة": "الجمعة",
    "السبت": "السبت",   "سبت": "السبت",
}
