"""
test_parser.py - اختبار وحدة قراءة الـ PDF دون تشغيل البوت
"""
import sys
from pdf_parser import parse_schedule_pdf

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "sample_schedule.pdf"
    print(f"🔍 تحليل: {path}\n")
    try:
        sessions = parse_schedule_pdf(path)
        if not sessions:
            print("⚠️ لم يتم استخراج أي حصص.")
        else:
            print(f"✅ تم استخراج {len(sessions)} حصة:\n")
            for i, s in enumerate(sessions, 1):
                print(
                    f"{i:2}. {s['subject']:<20} "
                    f"{s['day']:<10} "
                    f"{s['start_time']}-{s['end_time']}  "
                    f"{s['room']}"
                )
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
