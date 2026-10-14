# 📚 دليل تشغيل بوت إدارة الجداول الدراسية

## 🗂️ هيكل المشروع

```
telegram-schedule-bot/
│
├── main.py              ← نقطة الدخول الرئيسية (تشغيل البوت)
├── config.py            ← الإعدادات المركزية
├── database.py          ← طبقة قاعدة بيانات SQLite
├── handlers.py          ← جميع معالجات الأوامر والأزرار
├── scheduler.py         ← نظام الجدولة والتنبيهات
├── pdf_parser.py        ← محلّل ملفات PDF
├── keyboards.py         ← لوحات المفاتيح التفاعلية
│
├── requirements.txt     ← المتطلبات
├── .env.example         ← نموذج ملف الإعدادات
├── create_sample_pdf.py ← أداة لإنشاء PDF تجريبي
└── test_parser.py       ← اختبار محلّل PDF
```

---

## ⚙️ خطوات الإعداد والتشغيل

### 1️⃣ الحصول على توكن البوت

1. افتح تيليجرام وابحث عن **@BotFather**
2. أرسل الأمر `/newbot`
3. اختر اسماً للبوت ثم اسم مستخدم (ينتهي بـ `bot`)
4. ستحصل على **توكن** بالشكل: `123456789:ABCdefGhIJKl...`

### 2️⃣ معرفة Telegram ID الخاص بك

ابحث عن **@userinfobot** في تيليجرام وأرسله أي رسالة، سيردّ بمعرّفك.

### 3️⃣ معرفة ID المجموعة

1. أضف البوت إلى المجموعة
2. أضف **@userinfobot** إلى المجموعة أيضاً
3. أرسل أي رسالة في المجموعة، سيردّ بـ Group ID (رقم سالب)

### 4️⃣ إعداد ملف البيئة

```bash
# انسخ ملف المثال
cp .env.example .env

# عدّل القيم
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUvwXyZ
ADMIN_IDS=123456789,987654321
GROUP_CHAT_ID=-1001234567890
REMINDER_MINUTES_BEFORE=15
```

### 5️⃣ تثبيت المتطلبات

```bash
# إنشاء بيئة افتراضية (موصى به)
python -m venv venv

# تفعيل البيئة (Windows)
venv\Scripts\activate

# تفعيل البيئة (Linux/macOS)
source venv/bin/activate

# تثبيت المكتبات
pip install -r requirements.txt
```

### 6️⃣ تشغيل البوت

```bash
python main.py
```

---

## 📦 شرح المكتبات

| المكتبة | الوصف |
|---------|-------|
| `python-telegram-bot[job-queue]==21.6` | المكتبة الرئيسية للتواصل مع Telegram API (v20+, async) |
| `APScheduler==3.10.4` | جدولة المهام المتكررة (CronTrigger أسبوعي للتنبيهات) |
| `pdfplumber==0.11.0` | استخراج الجداول والنصوص من PDF بدقة عالية |
| `python-dotenv==1.0.1` | قراءة ملف `.env` لإدارة المتغيرات البيئية |

---

## 🤖 أوامر البوت

### للجميع وللطلاب:
| الأمر | الوظيفة |
|-------|---------|
| `/start` | تسجيل في البوت وعرض رسالة الترحيب |
| `/schedule` أو `/today` | عرض حصص اليوم الحالي |
| `/next` | معرفة الحصة القادمة فوراً والوقت المتبقي لبدئها |
| `/tomorrow` | عرض جدول الغد كاملاً |
| `/fullschedule` | عرض الجدول الأسبوعي الكامل لجميع الأيام |
| `/stats` | عرض حالة البوت وإحصائيات الحصص والأعضاء |

### للمشرفين فقط:
| الأمر | الوظيفة |
|-------|---------|
| `/panel` | فتح لوحة التحكم الرئيسية (تعديل القاعات والأوقات) |
| `/settopic` | تعيين التوبك الحالي في المجموعة لوصول التنبيهات إليه |
| `/testalert` | إرسال تنبيه تجريبي فوراً لاختبار التوبك |
| `/pause` | إيقاف التنبيهات التلقائية مؤقتاً (مثلاً أثناء الإجازة) |
| `/resume` | استئناف التنبيهات التلقائية |
| `/addadmin <id>` | إضافة مشرف جديد |
| `/removeadmin <id>` | إزالة مشرف |
| إرسال ملف PDF | رفع جدول جديد واستخراجه تلقائياً |

---

## 🔔 نظام التنبيهات

```
كل حصة → يُنشئ البوت مهمة أسبوعية متكررة (CronTrigger)
قبل 15 دقيقة من بدء الحصة → يُرسَل تنبيه للمجموعة يحتوي:
  • اسم المادة
  • اليوم والتوقيت (من → إلى)  
  • رقم القاعة ونوعها (CC أو عادية)
  • منشن (@username) لكل الأعضاء المسجّلين
```

---

## 📋 بنية جدول الـ PDF المدعوم

يجب أن يحتوي الجدول على الأعمدة التالية (بأي لغة):

| Subject / المادة | Day / اليوم | Start Time / البداية | End Time / النهاية | Room / القاعة |
|---|---|---|---|---|
| Mathematics | Monday | 08:00 | 09:30 | CC 1 |

> **ملاحظة:** يدعم البوت أيام الأسبوع بالعربية والإنجليزية.

---

## 🏫 الغرف المتاحة

| النوع | الغرف |
|-------|-------|
| 🖥️ CC Rooms | CC 1 — CC 6 |
| 🏫 Normal Rooms | Room 1 — Room 18 |

---

## 🚀 التشغيل على سيرفر (VPS/Cloud)

```bash
# باستخدام screen (للإبقاء على البوت يعمل)
screen -S schedulebot
python main.py
# Ctrl+A ثم D للخروج مع الإبقاء على التشغيل

# باستخدام systemd service (موصى به للإنتاج)
# أنشئ /etc/systemd/system/schedulebot.service:
[Unit]
Description=Telegram Schedule Bot
After=network.target

[Service]
WorkingDirectory=/path/to/telegram-schedule-bot
ExecStart=/path/to/venv/bin/python main.py
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target

# فعّل الخدمة:
sudo systemctl enable schedulebot
sudo systemctl start schedulebot
```

---

## 🛠️ اختبار محلّل PDF

```bash
# أنشئ PDF تجريبياً أولاً
pip install reportlab
python create_sample_pdf.py

# اختبر المحلّل
python test_parser.py sample_schedule.pdf
```

---

## ⚠️ ملاحظات مهمة

> [!IMPORTANT]
> عدّل المنطقة الزمنية في `scheduler.py` من `"Asia/Riyadh"` إلى منطقتك:
> - السعودية/الكويت: `Asia/Riyadh`
> - مصر: `Africa/Cairo`
> - الإمارات: `Asia/Dubai`
> - المغرب: `Africa/Casablanca`

> [!NOTE]
> عند رفع PDF جديد، **يتم مسح جميع الحصص القديمة تلقائياً** واستبدالها بالجدول الجديد.

> [!TIP]
> لاختبار التنبيهات فوراً دون الانتظار، عدّل قيمة `REMINDER_MINUTES_BEFORE` في ملف `.env` ثم أعد تشغيل البوت.
