"""
seed_data.py - ملء قاعدة البيانات بمعلومات الجدول الأسبوعي المعطى
"""
import sys
import os

# إضافة المجلد الحالي للمسار
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database import init_db, clear_all_sessions, insert_session, get_all_sessions

# قائمة الحصص المستخرجة بدقة من جدول المحاضرات (Semester 1 - 2026/2027)
SCHEDULE_DATA = [
    # ── الأحد (Sunday) ──
    {
        "subject": "Networks I course (Boubiche Djallel)",
        "day": "الأحد",
        "start_time": "08:30",
        "end_time": "10:00",
        "room": "Room 7",
    },
    {
        "subject": "Networks I course (Boubiche Djallel)",
        "day": "الأحد",
        "start_time": "10:00",
        "end_time": "11:30",
        "room": "Room 7",
    },
    {
        "subject": "Networks I Tu (Boubiche Djallel)",
        "day": "الأحد",
        "start_time": "11:30",
        "end_time": "13:00",
        "room": "Room 7",
    },
    {
        "subject": "Operating Systems course (Guezouli Lyamine)",
        "day": "الأحد",
        "start_time": "14:00",
        "end_time": "15:30",
        "room": "Room 7",
    },
    {
        "subject": "Operating Systems Tu (Guezouli Lyamine)",
        "day": "الأحد",
        "start_time": "15:30",
        "end_time": "17:00",
        "room": "Room 7",
    },

    # ── الاثنين (Monday) ──
    {
        "subject": "Advanced Data base PW (Guezzouli Larbi)",
        "day": "الاثنين",
        "start_time": "08:30",
        "end_time": "10:00",
        "room": "Room 21",
    },
    {
        "subject": "Operating Systems PW SGr1/SGr2 - Group 1 (Guezouli Lyamine)",
        "day": "الاثنين",
        "start_time": "10:00",
        "end_time": "13:00",
        "room": "CC 3",
    },
    {
        "subject": "Signal Processing TU (SAIDI Raouia)",
        "day": "الاثنين",
        "start_time": "14:00",
        "end_time": "15:30",
        "room": "Room 8",
    },
    {
        "subject": "Signal Processing course (SAIDI Raouia)",
        "day": "الاثنين",
        "start_time": "15:30",
        "end_time": "17:00",
        "room": "Room 8",
    },

    # ── الثلاثاء (Tuesday) ──
    {
        "subject": "English 1 (Lebbal, Farida)",
        "day": "الثلاثاء",
        "start_time": "08:30",
        "end_time": "10:00",
        "room": "Amphi 3",
    },
    {
        "subject": "Computer Architecture course (Chenna, A.)",
        "day": "الثلاثاء",
        "start_time": "10:00",
        "end_time": "11:30",
        "room": "Room 7",
    },
    {
        "subject": "Computer Architecture Tu (Chenna, A.)",
        "day": "الثلاثاء",
        "start_time": "11:30",
        "end_time": "13:00",
        "room": "Room 7",
    },

    # ── الأربعاء (Wednesday) ──
    {
        "subject": "Networks I PW - Group 1 (Boubiche Djallel)",
        "day": "الأربعاء",
        "start_time": "08:30",
        "end_time": "11:30",
        "room": "CC 2",
    },
    {
        "subject": "Object-Oriented Programming PW - Group 2 (HADJI Oussama)",
        "day": "الأربعاء",
        "start_time": "08:30",
        "end_time": "11:30",
        "room": "CC 5",
    },
    {
        "subject": "Object-Oriented Programming course (HADJI Oussama)",
        "day": "الأربعاء",
        "start_time": "11:30",
        "end_time": "13:00",
        "room": "Room 7",
    },
    {
        "subject": "Object-Oriented Programming Tu (HADJI Oussama)",
        "day": "الأربعاء",
        "start_time": "14:00",
        "end_time": "15:30",
        "room": "Room 7",
    },
    {
        "subject": "TIC (Athmani, Samir)",
        "day": "الأربعاء",
        "start_time": "15:30",
        "end_time": "17:00",
        "room": "Room 7",
    },

    # ── الخميس (Thursday) ──
    {
        "subject": "Renewable Energies and Energy Efficiency (Mechnane Farouk)",
        "day": "الخميس",
        "start_time": "08:30",
        "end_time": "10:00",
        "room": "Room 7",
    },
    {
        "subject": "Advanced Data base - course (Guezzouli Larbi)",
        "day": "الخميس",
        "start_time": "10:00",
        "end_time": "11:30",
        "room": "Room 7",
    },
    {
        "subject": "Advanced Data base - TU (Guezzouli Larbi)",
        "day": "الخميس",
        "start_time": "11:30",
        "end_time": "13:00",
        "room": "Room 7",
    },
]

def seed():
    print("🔄 تهيئة قاعدة البيانات...")
    init_db()
    clear_all_sessions()
    
    count = 0
    for item in SCHEDULE_DATA:
        insert_session(
            subject=item["subject"],
            day=item["day"],
            start_time=item["start_time"],
            end_time=item["end_time"],
            room=item["room"],
        )
        count += 1
        print(f"  [+] تم إضافة: {item['day']} | {item['start_time']} - {item['end_time']} | {item['room']} | {item['subject']}")
    
    print(f"\n✅ تم بنجاح إضافة {count} حصة دراسية في قاعدة البيانات!")

if __name__ == "__main__":
    seed()
