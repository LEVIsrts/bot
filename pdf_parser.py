"""
pdf_parser.py - استخراج جدول الحصص من ملف PDF
"""
import re
import logging
from pathlib import Path
from typing import Optional

import pdfplumber

from config import DAY_MAP, ALL_ROOMS

logger = logging.getLogger(__name__)

# ── أنماط Regex للتعرف على الأوقات ──────────────────────────────────────────────
TIME_PATTERN = re.compile(
    r"(\d{1,2})[:\.](\d{2})\s*(?:am|pm|AM|PM)?",
    re.IGNORECASE,
)
TIME_RANGE_PATTERN = re.compile(
    r"(\d{1,2})[:\.](\d{2})\s*[-–—]\s*(\d{1,2})[:\.](\d{2})",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════
#  الدوال المساعدة
# ══════════════════════════════════════════════════════════════

def _normalize_time(hour: int, minute: int, raw: str = "") -> str:
    """حوّل الساعة إلى صيغة HH:MM بعد معالجة AM/PM."""
    raw_lower = raw.lower()
    if "pm" in raw_lower and hour != 12:
        hour += 12
    if "am" in raw_lower and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _extract_time_range(text: str) -> Optional[tuple[str, str]]:
    """استخرج نطاق الوقت من نص مثل '08:00 - 09:30' أو '8am-9:30pm'."""
    m = TIME_RANGE_PATTERN.search(text)
    if m:
        start = _normalize_time(int(m.group(1)), int(m.group(2)), text)
        end   = _normalize_time(int(m.group(3)), int(m.group(4)), text)
        return start, end
    # fallback: بحث عن وقتين منفصلين
    times = TIME_PATTERN.findall(text)
    if len(times) >= 2:
        start = _normalize_time(int(times[0][0]), int(times[0][1]), text)
        end   = _normalize_time(int(times[1][0]), int(times[1][1]), text)
        return start, end
    return None


def _normalize_day(text: str) -> Optional[str]:
    """حوّل اسم اليوم (عربي أو إنجليزي) إلى الصيغة العربية الموحّدة."""
    text_lower = text.strip().lower()
    for key, value in DAY_MAP.items():
        if key.lower() in text_lower:
            return value
    return None


def _find_room(text: str) -> Optional[str]:
    """ابحث عن اسم غرفة مذكور في النص."""
    text_upper = text.upper()
    # CC rooms أولاً
    for room in ALL_ROOMS:
        if room.upper() in text_upper:
            return room
    # بحث عام
    m = re.search(r"(CC\s*\d+|Room\s*\d+|غرفة\s*\d+|قاعة\s*\d+)", text, re.IGNORECASE)
    if m:
        return m.group(0).strip()
    return None


# ══════════════════════════════════════════════════════════════
#  المحلّل الرئيسي
# ══════════════════════════════════════════════════════════════

def parse_schedule_pdf(pdf_path: str) -> list[dict]:
    """
    حلّل ملف PDF وأرجع قائمة من الحصص على شكل:
    [
        {
            "subject":    "Mathematics",
            "day":        "الاثنين",
            "start_time": "08:00",
            "end_time":   "09:30",
            "room":       "CC 2",
        },
        ...
    ]
    """
    sessions: list[dict] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                logger.info(f"📄 معالجة الصفحة {page_num}")

                # ── محاولة 1: استخراج جداول منظمة ────────────────────────────
                tables = page.extract_tables()
                for table in tables:
                    sessions.extend(_parse_table(table))

                # ── محاولة 2: إذا لم توجد جداول, استخرج النص مباشرة ──────────
                if not tables:
                    text = page.extract_text() or ""
                    sessions.extend(_parse_raw_text(text))

    except Exception as e:
        logger.error(f"❌ خطأ في قراءة PDF: {e}")
        raise

    # إزالة التكرارات
    seen = set()
    unique: list[dict] = []
    for s in sessions:
        key = (s["subject"], s["day"], s["start_time"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    logger.info(f"✅ تم استخراج {len(unique)} حصة من الملف.")
    return unique


def _parse_table(table: list[list]) -> list[dict]:
    """حلّل جدولاً منظماً مستخرجاً من pdfplumber."""
    sessions: list[dict] = []
    if not table or len(table) < 2:
        return sessions

    # كشف رؤوس الأعمدة (الصف الأول)
    headers = [str(h).strip().lower() if h else "" for h in table[0]]

    # دالة مساعدة لإيجاد عمود بالكلمة المفتاحية
    def col_idx(keywords: list[str]) -> int:
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return -1

    idx_subject = col_idx(["subject", "course", "مادة", "المادة", "الحصة"])
    idx_day     = col_idx(["day", "يوم", "اليوم"])
    idx_time    = col_idx(["time", "وقت", "الوقت", "توقيت"])
    idx_start   = col_idx(["start", "بداية", "من"])
    idx_end     = col_idx(["end", "نهاية", "إلى", "الى"])
    idx_room    = col_idx(["room", "hall", "قاعة", "غرفة", "cc"])

    for row in table[1:]:
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue

        def cell(idx: int) -> str:
            if idx < 0 or idx >= len(row):
                return ""
            return str(row[idx]).strip() if row[idx] else ""

        subject = cell(idx_subject)
        day_raw = cell(idx_day)
        room    = cell(idx_room) or _find_room(" ".join(str(c) for c in row if c))

        # الوقت
        time_range: Optional[tuple[str, str]] = None
        if idx_time >= 0:
            time_range = _extract_time_range(cell(idx_time))
        if not time_range and idx_start >= 0 and idx_end >= 0:
            start_text = cell(idx_start)
            end_text   = cell(idx_end)
            if start_text and end_text:
                st = TIME_PATTERN.search(start_text)
                et = TIME_PATTERN.search(end_text)
                if st and et:
                    time_range = (
                        _normalize_time(int(st.group(1)), int(st.group(2)), start_text),
                        _normalize_time(int(et.group(1)), int(et.group(2)), end_text),
                    )

        day = _normalize_day(day_raw) if day_raw else None

        if subject and day and time_range and room:
            sessions.append({
                "subject":    subject,
                "day":        day,
                "start_time": time_range[0],
                "end_time":   time_range[1],
                "room":       room,
            })

    return sessions


def _parse_raw_text(text: str) -> list[dict]:
    """
    محاولة استخراج الحصص من نص حر عندما لا يوجد جدول منظم.
    يبحث عن أسطر تحتوي على: يوم + وقت + مادة + غرفة.
    """
    sessions: list[dict] = []
    lines = text.split("\n")

    current_day: Optional[str] = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # هل السطر يحتوي على اسم يوم فقط؟
        possible_day = _normalize_day(line)
        if possible_day and len(line.split()) <= 3:
            current_day = possible_day
            continue

        # هل السطر يحتوي على نطاق زمني؟
        time_range = _extract_time_range(line)
        if not time_range:
            continue

        day    = _normalize_day(line) or current_day
        room   = _find_room(line)
        # اسم المادة: ما تبقى بعد حذف الوقت والغرفة واليوم
        subject_text = re.sub(
            r"\d{1,2}[:.]\d{2}(\s*[-–—]\s*\d{1,2}[:.]\d{2})?", "", line
        )
        if room:
            subject_text = subject_text.replace(room, "")
        if day:
            subject_text = re.sub(day, "", subject_text, flags=re.IGNORECASE)
        subject = subject_text.strip(" -–—|,.")

        if subject and day and room:
            sessions.append({
                "subject":    subject,
                "day":        day,
                "start_time": time_range[0],
                "end_time":   time_range[1],
                "room":       room,
            })

    return sessions
