"""
create_sample_pdf.py - ينشئ ملف PDF تجريبي للاختبار
شغّله مرة واحدة فقط: python create_sample_pdf.py
"""
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

import csv

# البيانات التجريبية
SAMPLE_DATA = [
    ["Subject",      "Day",       "Start Time", "End Time", "Room"],
    ["Mathematics",  "Monday",    "08:00",      "09:30",    "CC 1"],
    ["Physics",      "Monday",    "10:00",      "11:30",    "Room 5"],
    ["Chemistry",    "Tuesday",   "08:00",      "09:30",    "CC 2"],
    ["Biology",      "Tuesday",   "11:00",      "12:30",    "Room 10"],
    ["English",      "Wednesday", "09:00",      "10:30",    "CC 3"],
    ["History",      "Wednesday", "13:00",      "14:30",    "Room 3"],
    ["Geography",    "Thursday",  "08:00",      "09:30",    "CC 4"],
    ["Computer Sci", "Thursday",  "10:00",      "11:30",    "CC 5"],
    ["Arabic",       "Sunday",    "08:00",      "09:30",    "Room 7"],
    ["PE",           "Sunday",    "11:00",      "12:00",    "Room 18"],
]


def create_pdf():
    if not HAS_REPORTLAB:
        print("❌ مكتبة reportlab غير مثبّتة.")
        print("   شغّل: pip install reportlab")
        print("   أو استخدم الملف sample_schedule.csv بدلاً منه")
        create_csv()
        return

    doc = SimpleDocTemplate("sample_schedule.pdf", pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("<b>Weekly Class Schedule</b>", styles["Title"]),
        Paragraph(" ", styles["Normal"]),
    ]

    table = Table(SAMPLE_DATA, colWidths=[4*cm, 3.5*cm, 3*cm, 3*cm, 3*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#2E4057")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTSIZE",    (0, 0), (-1, 0), 12),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE",    (0, 1), (-1, -1), 10),
        ("ROWHEIGHT",   (0, 0), (-1, -1), 1*cm),
    ]))

    elements.append(table)
    doc.build(elements)
    print("✅ تم إنشاء sample_schedule.pdf")


def create_csv():
    with open("sample_schedule.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(SAMPLE_DATA)
    print("✅ تم إنشاء sample_schedule.csv (بديل للـ PDF)")


if __name__ == "__main__":
    create_pdf()
    create_csv()
