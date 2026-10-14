"""
show_schedule.py - عرض محتوى قاعدة البيانات الحالية بشكل منظم
"""
import sqlite3
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def display():
    conn = sqlite3.connect("schedule.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, day, start_time, end_time, room, subject, is_cancelled FROM sessions ORDER BY id")
    rows = cursor.fetchall()
    
    print("\n" + "="*85)
    print(f"{'ID':<4} | {'اليوم':<9} | {'الوقت':<13} | {'القاعة':<10} | {'المادة والأستاذ'}")
    print("="*85)
    
    for r in rows:
        status = " (ملغى)" if r[6] else ""
        print(f"{r[0]:<4} | {r[1]:<9} | {r[2]} - {r[3]:<5} | {r[4]:<10} | {r[5]}{status}")
        
    print("="*85)
    print(f"إجمالي الحصص المسجلة: {len(rows)}\n")
    conn.close()

if __name__ == "__main__":
    display()
