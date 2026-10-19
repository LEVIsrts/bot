"""
database.py - طبقة قاعدة البيانات (SQLite)
"""
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional
from config import DB_PATH

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  إدارة الاتصال
# ══════════════════════════════════════════════════════════════

@contextmanager
def get_conn():
    """Context manager يعطي اتصالاً بقاعدة البيانات مع commit/rollback تلقائي."""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
#  إنشاء الجداول
# ══════════════════════════════════════════════════════════════

def init_db() -> None:
    """أنشئ جميع الجداول إذا لم تكن موجودة."""
    with get_conn() as conn:
        conn.executescript("""
            -- جدول الحصص الدراسية
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject     TEXT    NOT NULL,          -- اسم المادة
                day         TEXT    NOT NULL,          -- اليوم بالعربية
                start_time  TEXT    NOT NULL,          -- HH:MM
                end_time    TEXT    NOT NULL,          -- HH:MM
                room        TEXT    NOT NULL,          -- CC 1 / Room 5 ...
                is_cancelled INTEGER NOT NULL DEFAULT 0,  -- 0=نشط  1=ملغى
                schedule_id TEXT,                      -- معرّف APScheduler
                created_at  TEXT    DEFAULT (datetime('now')),
                updated_at  TEXT    DEFAULT (datetime('now'))
            );

            -- جدول الأعضاء المسجلين في المجموعة (للمنشن)
            CREATE TABLE IF NOT EXISTS members (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                joined_at   TEXT DEFAULT (datetime('now'))
            );

            -- جدول المشرفين الديناميكيين (إضافة للـ config)
            CREATE TABLE IF NOT EXISTS admins (
                user_id     INTEGER PRIMARY KEY,
                added_by    INTEGER,
                added_at    TEXT DEFAULT (datetime('now'))
            );

            -- جدول سجل التنبيهات المُرسَلة
            CREATE TABLE IF NOT EXISTS alert_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER REFERENCES sessions(id),
                sent_at     TEXT DEFAULT (datetime('now')),
                status      TEXT  -- sent / failed
            );

            -- جدول إعدادات البوت الديناميكية (مثل topic_id)
            CREATE TABLE IF NOT EXISTS bot_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
    logger.info("✅ قاعدة البيانات جاهزة.")


# ══════════════════════════════════════════════════════════════
#  دوال الحصص (Sessions)
# ══════════════════════════════════════════════════════════════

def insert_session(subject: str, day: str, start_time: str, end_time: str, room: str) -> int:
    """أضف حصة جديدة وأرجع معرّفها."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO sessions (subject, day, start_time, end_time, room)
               VALUES (?, ?, ?, ?, ?)""",
            (subject, day, start_time, end_time, room),
        )
        return cur.lastrowid


DAY_ORDER_SQL = """
    CASE day
        WHEN 'الأحد' THEN 1
        WHEN 'الاثنين' THEN 2
        WHEN 'الثلاثاء' THEN 3
        WHEN 'الأربعاء' THEN 4
        WHEN 'الخميس' THEN 5
        WHEN 'الجمعة' THEN 6
        WHEN 'السبت' THEN 7
        ELSE 8
    END, start_time
"""


def get_all_sessions(include_cancelled: bool = False) -> list[sqlite3.Row]:
    """اجلب جميع الحصص مرتبةً زمنياً حسب أيام الأسبوع (الأحد → الخميس) ثم الوقت."""
    with get_conn() as conn:
        if include_cancelled:
            return conn.execute(
                f"SELECT * FROM sessions ORDER BY {DAY_ORDER_SQL}"
            ).fetchall()
        return conn.execute(
            f"SELECT * FROM sessions WHERE is_cancelled=0 ORDER BY {DAY_ORDER_SQL}"
        ).fetchall()


def get_session(session_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()


def get_sessions_by_day(day: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE day=? AND is_cancelled=0 ORDER BY start_time",
            (day,),
        ).fetchall()


def update_session_room(session_id: int, new_room: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET room=?, updated_at=datetime('now') WHERE id=?",
            (new_room, session_id),
        )


def update_session_time(session_id: int, start_time: str, end_time: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE sessions
               SET start_time=?, end_time=?, updated_at=datetime('now')
               WHERE id=?""",
            (start_time, end_time, session_id),
        )


def cancel_session(session_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET is_cancelled=1, updated_at=datetime('now') WHERE id=?",
            (session_id,),
        )


def restore_session(session_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET is_cancelled=0, updated_at=datetime('now') WHERE id=?",
            (session_id,),
        )


def delete_session(session_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))


def set_session_schedule_id(session_id: int, schedule_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET schedule_id=? WHERE id=?",
            (schedule_id, session_id),
        )


def clear_all_sessions() -> None:
    """امسح جميع الحصص (تستخدم عند رفع PDF جديد)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions")


# ══════════════════════════════════════════════════════════════
#  دوال الأعضاء (Members)
# ══════════════════════════════════════════════════════════════

def upsert_member(user_id: int, username: Optional[str], full_name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO members (user_id, username, full_name)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   username=excluded.username,
                   full_name=excluded.full_name""",
            (user_id, username, full_name),
        )


def get_all_members() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM members").fetchall()


def remove_member(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM members WHERE user_id=?", (user_id,))


def find_target_member(keywords: tuple[str, ...] = ("sofine", "traore")) -> Optional[dict]:
    """البحث في سجل الأعضاء عن عضو يحمل الاسم المطلوب لمنشنه تلقائياً."""
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id, username, full_name FROM members").fetchall()
        for r in rows:
            haystack = f"{r['full_name'] or ''} {r['username'] or ''}".lower()
            for kw in keywords:
                if kw.lower() in haystack:
                    return {
                        "id": r["user_id"],
                        "name": r["full_name"] or r["username"] or "Member",
                    }
    return None


# ══════════════════════════════════════════════════════════════
#  دوال المشرفين (Admins)
# ══════════════════════════════════════════════════════════════

def add_admin(user_id: int, added_by: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)",
            (user_id, added_by),
        )


def remove_admin(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))


def get_db_admins() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM admins").fetchall()
        return [r["user_id"] for r in rows]


# ══════════════════════════════════════════════════════════════
#  دوال سجل التنبيهات
# ══════════════════════════════════════════════════════════════

def log_alert(session_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alert_log (session_id, status) VALUES (?, ?)",
            (session_id, status),
        )


# ══════════════════════════════════════════════════════════════
#  دوال إعدادات البوت (Bot Settings)
# ══════════════════════════════════════════════════════════════

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO bot_settings (key, value)
               VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value),
        )


def get_user_lang(user_id: int) -> str:
    """الحصول على لغة واجهة المستخدم المفضلة ('ar' أو 'en'). الافتراضي هو 'ar'."""
    lang = get_setting(f"user_lang:{user_id}", "ar")
    return lang if lang in ("ar", "en") else "ar"


def set_user_lang(user_id: int, lang: str) -> None:
    """حفظ لغة واجهة المستخدم المفضلة ('ar' أو 'en')."""
    if lang in ("ar", "en"):
        set_setting(f"user_lang:{user_id}", lang)

