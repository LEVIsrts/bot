import logging
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import socket
import asyncio
import threading
import http.server

# حل مشكلة All connection attempts failed بإعطاء الأولوية لـ IPv4
if os.getenv("DISABLE_IPV6_FIX", "0") != "1":
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(*args, **kwargs):
        res = _orig_getaddrinfo(*args, **kwargs)
        ipv4 = [r for r in res if r[0] == socket.AF_INET]
        return ipv4 if ipv4 else res
    socket.getaddrinfo = _ipv4_getaddrinfo

from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db
from scheduler import create_scheduler, reschedule_all
from handlers import (
    cmd_start,
    cmd_panel,
    cmd_schedule,
    cmd_full_schedule,
    cmd_next,
    cmd_tomorrow,
    cmd_stats,
    cmd_set_topic,
    cmd_test_alert,
    cmd_pause_alerts,
    cmd_resume_alerts,
    cmd_add_admin,
    cmd_remove_admin,
    cmd_seed,
    cmd_set_translate_topic,
    cmd_set_translate_mode,
    cmd_set_translate_user,
    cmd_set_translate_target,
    cmd_bot_settings,
    handle_pdf,
    handle_callback,
    handle_text,
    handle_new_member,
    handle_left_member,
)

# ══════════════════════════════════════════════════════════════
#  إعداد التسجيل (Logging)
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)

# تخفيف رسائل مكتبات httpx/httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  خادم الفحص الحي (Render Health Check)
# ══════════════════════════════════════════════════════════════

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "2")
        self.end_headers()

    def log_message(self, format, *args):
        # منع إغراق سجلات اللوج بطلبات الفحص المتكررة
        pass


def start_health_server_thread() -> None:
    """
    تشغيل خادم HTTP فوري في ثريد مستقل للاستجابة لفحص المنافذ في Render Web Service
    وتجنب انتهاء المهلة (Port scan timeout / Timed Out).
    """
    port_str = os.getenv("PORT", "10000")
    try:
        port = int(port_str)
    except ValueError:
        port = 10000

    def run_server():
        try:
            server = http.server.HTTPServer(("0.0.0.0", port), HealthCheckHandler)
            logger.info(f"🌐 [Render Health Check] خادم الفحص الحي يعمل الآن بنجاح على 0.0.0.0:{port}")
            server.serve_forever()
        except Exception as e:
            logger.warning(f"⚠️ تعذر تشغيل خادم الفحص الحي على المنفذ {port}: {e}")

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()


# ══════════════════════════════════════════════════════════════
#  Callbacks دورة حياة التطبيق
# ══════════════════════════════════════════════════════════════

async def on_startup(application: Application) -> None:
    """تشغيل عمليات الإعداد عند بدء البوت."""
    logger.info("🚀 بدء تشغيل البوت...")

    # تهيئة قاعدة البيانات
    init_db()

    # تعبئة الجدول تلقائياً إذا كانت قاعدة البيانات جديدة/فارغة
    from database import get_all_sessions
    if not get_all_sessions(include_cancelled=True):
        logger.info("ℹ️ قاعدة البيانات فارغة، جاري تعبئة الجدول الدراسي تلقائياً...")
        try:
            from seed_data import seed
            seed()
        except Exception as e:
            logger.error(f"فشلت التعبئة التلقائية: {e}")

    # إنشاء وتشغيل المجدول
    scheduler = create_scheduler()
    application.bot_data["scheduler"] = scheduler
    scheduler.start()

    # جدولة تنبيهات الحصص الموجودة
    reschedule_all(scheduler, application.bot)

    logger.info("✅ البوت جاهز ويعمل!")
    logger.info(f"👥 مشرفون محددون مسبقاً: {ADMIN_IDS}")


async def on_shutdown(application: Application) -> None:
    """إيقاف المجدول عند إيقاف البوت."""
    scheduler = application.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 تم إيقاف المجدول.")


# ══════════════════════════════════════════════════════════════
#  تسجيل المعالجات
# ══════════════════════════════════════════════════════════════

def register_handlers(app: Application) -> None:
    # ── أوامر المستخدمين والطلاب ─────────────────────────────────
    app.add_handler(CommandHandler("start",          cmd_start))
    app.add_handler(CommandHandler("schedule",       cmd_schedule))
    app.add_handler(CommandHandler("today",          cmd_schedule))
    app.add_handler(CommandHandler("fullschedule",   cmd_full_schedule))
    app.add_handler(CommandHandler("next",           cmd_next))
    app.add_handler(CommandHandler("tomorrow",       cmd_tomorrow))
    app.add_handler(CommandHandler("stats",          cmd_stats))

    # ── أوامر المشرفين ───────────────────────────────────────────
    app.add_handler(CommandHandler("panel",          cmd_panel))
    app.add_handler(CommandHandler("settings",       cmd_bot_settings))
    app.add_handler(CommandHandler("settopic",       cmd_set_topic))
    app.add_handler(CommandHandler("translatetopic", cmd_set_translate_topic))
    app.add_handler(CommandHandler("translatemode",  cmd_set_translate_mode))
    app.add_handler(CommandHandler("setuser",        cmd_set_translate_user))
    app.add_handler(CommandHandler("settarget",      cmd_set_translate_target))
    app.add_handler(CommandHandler("testalert",      cmd_test_alert))
    app.add_handler(CommandHandler("pause",          cmd_pause_alerts))
    app.add_handler(CommandHandler("resume",         cmd_resume_alerts))
    app.add_handler(CommandHandler("seed",           cmd_seed))
    app.add_handler(CommandHandler("addadmin",       cmd_add_admin))
    app.add_handler(CommandHandler("removeadmin",    cmd_remove_admin))

    # ── معالج ملفات PDF ──────────────────────────────────────────
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    # ── أزرار لوحة التحكم ────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── رسائل نصية (لإدخال البيانات التفاعلي) ────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text,
    ))

    # ── انضمام/مغادرة الأعضاء ────────────────────────────────────
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER,  handle_left_member))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة أخطاء الشبكة والبروكسي بهدوء دون أن يتوقف البوت."""
    logger.warning(f"⚠️ خطأ مؤقت في الاتصال بالتيليجرام: {context.error}")


# ══════════════════════════════════════════════════════════════
#  نقطة الدخول
# ══════════════════════════════════════════════════════════════

def main() -> None:
    # تشغيل خادم الفحص الحي فوراً في الخلفية لتجاوز فحص المنفذ في Render
    start_health_server_thread()

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ لم يتم تحديد BOT_TOKEN. أضفه في ملف .env")
        sys.exit(1)

    import asyncio
    # توافقية بايثون 3.12 و 3.14+ (إنشاء event loop في الـ MainThread)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # إلغاء أي متغيرات بروكسي تالفة في النظام للاتصال المباشر
    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        os.environ.pop(var, None)

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    # بناء التطبيق بالاتصال المباشر
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    # تسجيل المعالجات ومعالج الأخطاء
    register_handlers(app)
    app.add_error_handler(error_handler)

    logger.info("▶️ تشغيل البوت في وضع Polling المباشر...")
    app.run_polling(
        allowed_updates=["message", "callback_query", "chat_member"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
