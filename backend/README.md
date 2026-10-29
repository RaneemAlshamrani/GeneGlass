# GeneGlass Backend

Backend مشروع GeneGlass بعد إكمال الإعداد وقاعدة البيانات والمصادقة. يحتوي حاليًا على:

- مشروع FastAPI منظم وقابل للتوسعة.
- إعداد CORS لعناوين frontend صريحة.
- تحميل الإعدادات من متغيرات البيئة وملف `.env`.
- `GET /health` لفحص حالة الخدمة.
- `GET /api` كنقطة دخول للـ API.
- قاعدة بيانات SQLite محلية باستخدام SQLAlchemy.
- جداول مترابطة للمستخدمين والتحليلات والمراجعات.
- تفعيل قيود المفاتيح الأجنبية في SQLite.
- تسجيل دخول فعلي عبر OAuth2 Password Flow وJWT.
- تشفير كلمات المرور باستخدام Argon2؛ لا تُحفظ كلمات المرور بصورتها الأصلية.
- حماية الصفحات الداخلية والتحقق من الجلسة عبر `GET /api/auth/me`.
- اختبارات آلية للنقاط الأساسية وCORS وقاعدة البيانات.

لم يُنفّذ رفع ملفات JAK2 أو فحص V617F بعد. بيانات التحليلات الظاهرة حاليًا في Dashboard ما زالت عرضًا ثابتًا وليست نتائج مخبرية حقيقية.

## التشغيل على Windows PowerShell

نفّذ الأوامر من داخل مجلد `backend`:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

إذا منع PowerShell تشغيل ملف التفعيل، يمكن تجاوز التفعيل واستخدام Python داخل البيئة مباشرة:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

الخادم المحلي: <http://127.0.0.1:8000>

## التشغيل على macOS أو Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m uvicorn app.main:app --reload
```

خيار `--reload` مخصص للتطوير المحلي فقط.

## الاختبار

بعد تثبيت المتطلبات ومن داخل `backend`:

```powershell
python -m pytest
```

اختبار يدوي من PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api
```

استجابة `/health` تتضمن `"database": "connected"` عند نجاح اتصال SQLite.

ويمكن فتح التوثيق التفاعلي:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

## ربط الـ frontend

الـ frontend الموجود في المستودع HTML/CSS/JavaScript ثابت، ويمكن تشغيله من **جذر المشروع** بخادم Python بسيط:

```powershell
python -m http.server 5500
```

ثم افتح صفحة الدخول:

<http://127.0.0.1:5500/LoginPage/login.html>

الإعداد الافتراضي في `.env.example` يسمح للمنفذ `5500`. إذا شغّلت الواجهة بعنوان مختلف، عدّل `CORS_ORIGINS` في `.env` مع تضمين البروتوكول والمنفذ. مثال:

```dotenv
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

واجعل عنوان API الأساسي في إعدادات الـ frontend مساويًا لـ:

```text
http://127.0.0.1:8000
```

لم تُضف اتصالات API إلى صفحات الواجهة في هذه المهمة لأن المسارات الوظيفية للمصادقة والتحليل والسجل لم تُنفّذ بعد. إضافة طلبات وهمية الآن ستعطي تكاملًا شكليًا لا يعمل.

## قاعدة البيانات

المسار الافتراضي لملف SQLite:

```text
backend/data/geneglass.db
```

يمكن تغييره من `.env`:

```dotenv
DATABASE_PATH=data/geneglass.db
```

تهيئة الجداول أو التأكد من وجودها عملية غير مدمرة؛ فهي تنشئ الجداول الناقصة ولا تحذف البيانات:

```powershell
python -m app.db.init_db
```

الجداول الحالية:

- `users`: بيانات الحساب الأساسية، الدور، حالة الحساب، وحقل hash لكلمة المرور سيُستخدم في مهمة المصادقة.
- `analyses`: ملف AB1 المرتبط بالمستخدم، حالة المعالجة، JAK2/V617F، حالة الجودة والنتيجة المستقبلية.
- `reviews`: قرار المراجع وتعليقه وربطه بالتحليل والمستخدم المراجع.

لا توجد بيانات Seed افتراضية؛ لذلك تبدأ الجداول فارغة.

## تسجيل الدخول والمصادقة

المسارات:

- `POST /api/auth/login`: يستقبل OAuth2 form باسمَي `username` و`password`. قيمة `username` هي البريد الإلكتروني.
- `GET /api/auth/me`: يعيد بيانات المستخدم الحالي ويتطلب `Authorization: Bearer <token>`.

مدة التوكن الافتراضية 60 دقيقة، ويمكن تغييرها في `.env` عبر:

```dotenv
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

أنشئ مفتاح JWT مختلفًا لكل بيئة ولا ترفع ملف `.env` إلى Git. لتوليد مفتاح:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

إنشاء مستخدم جديد يتم تفاعليًا حتى لا تظهر كلمة المرور في سجل الأوامر:

```powershell
python -m app.cli.create_user `
  --email specialist@example.com `
  --full-name "Dr. Rawan" `
  --department "Genetics Laboratory" `
  --role specialist
```

ستُطلب كلمة المرور وتأكيدها، ويجب ألا تقل عن 12 حرفًا.

## البنية

```text
backend/
├── app/
│   ├── api/          # HTTP routes
│   ├── cli/          # Interactive user administration
│   ├── core/         # Environment configuration
│   ├── db/           # SQLite engine, sessions, and initialization
│   ├── models/       # Users, analyses, and reviews
│   ├── schemas/      # Request/response schemas
│   ├── services/     # Password, JWT, and user services
│   └── main.py       # FastAPI application entry point
├── tests/
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```
