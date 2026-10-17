"""
pdf_parser.py - استخراج جدول الحصص من ملف PDF
يدعم كلا النموذجين:
1. الجداول المصفوفية (Grid/Matrix Timetables) حيث الأوقات في الأعمدة والأيام في الصفوف (شائعة في الجامعات).
2. الجداول العمودية (Columnar Timetables) حيث كل عمود يمثل حقلاً (المادة، اليوم، الوقت، القاعة).
3. النصوص الحرة (Fallback).
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
    if not text:
        return None
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
    """حوّل اسم اليوم (عربي أو إنجليزي أو فرنسي) إلى الصيغة العربية الموحّدة."""
    if not text:
        return None
    cleaned = text.strip().lower()
    if cleaned in DAY_MAP:
        return DAY_MAP[cleaned]
    # فرز المفاتيح من الأطول للأقصر لتجنب مطابقة الاختصارات الصغيرة خطأ
    sorted_keys = sorted(DAY_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if len(key) > 2:
            if re.search(r"\b" + re.escape(key) + r"\b", cleaned, re.IGNORECASE):
                return DAY_MAP[key]
        else:
            # المفاتيح المكونة من حرفين (مثل su, mo, tu) ككلمة كاملة فقط
            if re.search(r"\b" + re.escape(key) + r"\b", cleaned, re.IGNORECASE):
                return DAY_MAP[key]
    return None


def _find_room(text: str) -> Optional[str]:
    """ابحث عن اسم غرفة مذكور في النص ونسقه بشكل موحد."""
    if not text:
        return None
    text_upper = text.upper()
    for room in ALL_ROOMS:
        if re.search(r"\b" + re.escape(room.upper()) + r"\b", text_upper):
            return room
    m = re.search(r"\b(CC\s*\d+|Room\s*\d+|Amphi\s*\d+|قاعة\s*\d+|مدرج\s*\d+)\b", text, re.IGNORECASE)
    if m:
        raw = m.group(0).strip()
        m_norm = re.match(r"(?i)(cc|room|amphi|قاعة|مدرج)\s*(\d+)", raw)
        if m_norm:
            prefix = m_norm.group(1).upper()
            if prefix == "ROOM":
                prefix = "Room"
            elif prefix == "AMPHI":
                prefix = "Amphi"
            return f"{prefix} {m_norm.group(2)}"
        return raw
    return None


def _is_grid_table(table: list[list]) -> bool:
    """يتحقق مما إذا كان الجدول بنظام المصفوفة (الأوقات في صف الرأس والأيام في الصفوف)."""
    if not table or len(table) < 2:
        return False
    for r_idx in range(min(3, len(table))):
        times_count = sum(1 for cell in table[r_idx] if cell and _extract_time_range(str(cell)))
        if times_count >= 2:
            return True
    return False


# ══════════════════════════════════════════════════════════════
#  محلل جداول المصفوفة (Grid / Matrix)
# ══════════════════════════════════════════════════════════════

def _parse_grid_table(table: list[list]) -> list[dict]:
    """
    حلّل جدول مصفوفة (Grid / Matrix Timetable):
    - الصف العلوي يحتوي على نطاقات الأوقات (مثل 08:30 - 10:00).
    - العمود الأول يحتوي على الأيام (مثل Su, Mo, Tu أو الأحد, الاثنين).
    - الخلايا تحتوي على المادة، الأستاذ، والقاعة.
    """
    sessions: list[dict] = []
    if not table or len(table) < 2:
        return sessions

    # العثور على صف الأوقات
    header_row_idx = -1
    col_times: dict[int, tuple[str, str]] = {}
    for r_idx in range(min(3, len(table))):
        times_in_row = {}
        for col_idx, cell in enumerate(table[r_idx]):
            if not cell:
                continue
            tr = _extract_time_range(str(cell))
            if tr:
                times_in_row[col_idx] = tr
        if len(times_in_row) >= 2 and len(times_in_row) > len(col_times):
            col_times = times_in_row
            header_row_idx = r_idx

    if not col_times or header_row_idx == -1:
        return sessions

    current_day: Optional[str] = None

    for r_idx in range(header_row_idx + 1, len(table)):
        row = table[r_idx]
        if not row:
            continue

        raw_day = str(row[0]).strip() if row[0] is not None else ""
        day = _normalize_day(raw_day)
        if day:
            current_day = day
        elif not current_day:
            continue

        for col_idx in range(1, len(row)):
            if col_idx not in col_times:
                continue
            cell = row[col_idx]
            if not cell or not str(cell).strip():
                continue

            cell_text = str(cell).strip()
            st, et = col_times[col_idx]

            # تجاهل فترات الغداء / الاستراحة الشائعة إذا لم تكن تحتوي على حصة
            if st == "13:00" and et == "14:00" and not _find_room(cell_text):
                continue

            # في حصص المخابر / الأعمال التطبيقية (PW / TP)، قد تمتد الحصة إلى الخانة التالية الفارغة (حتى 3 ساعات)
            next_col = col_idx + 1
            if ("PW" in cell_text.upper() or "TP" in cell_text.upper()) and next_col in col_times:
                next_st, next_et = col_times[next_col]
                # لا تمتد خلال استراحة الغداء، ويجب أن تكون الخانة التالية فارغة
                if next_st < "13:00" and (next_col >= len(row) or not row[next_col] or not str(row[next_col]).strip()):
                    et = next_et

            room = _find_room(cell_text) or "قاعة غير محددة"

            # استخراج اسم المادة والأستاذ بعد حذف القاعة
            clean_text = cell_text
            if room and room != "قاعة غير محددة":
                clean_text = re.sub(r"\b" + re.escape(room) + r"\b", "", clean_text, flags=re.IGNORECASE)
                raw_room_compact = room.replace(" ", "")
                clean_text = re.sub(r"\b" + re.escape(raw_room_compact) + r"\b", "", clean_text, flags=re.IGNORECASE)

            lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
            subject = " - ".join(lines) if lines else cell_text

            sessions.append({
                "subject": subject,
                "day": current_day,
                "start_time": st,
                "end_time": et,
                "room": room,
            })

    return sessions


# ══════════════════════════════════════════════════════════════
#  محلل الجداول العمودية (Columnar Table)
# ══════════════════════════════════════════════════════════════

def _parse_columnar_table(table: list[list]) -> list[dict]:
    """حلّل جدولاً عمودياً (أعمدة: المادة، اليوم، الوقت، القاعة)."""
    sessions: list[dict] = []
    if not table or len(table) < 2:
        return sessions

    # كشف رؤوس الأعمدة (الصف الأول)
    headers = [str(h).strip().lower() if h else "" for h in table[0]]

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

_parse_table = _parse_columnar_table  # للتوافقية مع أي استدعاء قديم


# ══════════════════════════════════════════════════════════════
#  محلل النصوص الحرة (Raw Text Fallback)
# ══════════════════════════════════════════════════════════════

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

        possible_day = _normalize_day(line)
        if possible_day and len(line.split()) <= 3:
            current_day = possible_day
            continue

        time_range = _extract_time_range(line)
        if not time_range:
            continue

        day    = _normalize_day(line) or current_day
        room   = _find_room(line)
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

                tables = page.extract_tables()
                page_sessions: list[dict] = []
                for table in tables:
                    if _is_grid_table(table):
                        logger.info("📊 تم التعرف على جدول مصفوفي (Grid Table)")
                        page_sessions.extend(_parse_grid_table(table))
                    else:
                        logger.info("📋 تم التعرف على جدول أعمدة (Columnar Table)")
                        page_sessions.extend(_parse_columnar_table(table))

                if not page_sessions:
                    text = page.extract_text() or ""
                    page_sessions.extend(_parse_raw_text(text))

                sessions.extend(page_sessions)

    except Exception as e:
        logger.error(f"❌ خطأ في قراءة PDF: {e}")
        raise

    # إزالة التكرارات مع الحفاظ على الترتيب
    seen = set()
    unique: list[dict] = []
    for s in sessions:
        key = (s["subject"], s["day"], s["start_time"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    logger.info(f"✅ تم استخراج {len(unique)} حصة من الملف.")
    return unique
