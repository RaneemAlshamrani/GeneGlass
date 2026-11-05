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
- رفع ملفات AB1 مع التحقق من الامتداد والتوقيع والحجم وSHA-256.
- منع رفع الملف نفسه أكثر من مرة للمستخدم نفسه.
- قراءة تسلسل Sanger ودرجات Phred وعرض Chromatogram تفاعلي.
- محاذاة JAK2 المبدئية في الاتجاهين وتحديد موضع V617F المرجعي.
- عرض ارتفاعات A/C/G/T ونسبة القمة الثانوية إلى الأساسية وأسباب Needs Review.
- مستويات Original/Light/Medium/Strong لتنعيم عرض الإشارة بصريًا، مع إبقاء الإشارة الأصلية ظاهرة وإجراء QC والتحليل على البيانات الأصلية فقط.
- ربط مرجعي مباشر بسجل NCBI ClinVar من دون استنتاج تشخيصي.
- فحص بحثي اختياري لاختلافات SNV الظاهرة في base calls ضمن الجزء المقروء من JAK2، مع بحث ClinVar باستخدام HGVS فقط وتخزين النتائج مؤقتًا.
- مسار Specialist Review لحفظ قبول الأدلة أو رفضها أو طلب بيانات إضافية مع تعليق وسجل زمني كامل.
- حفظ الأدلة المبدئية في SQLite وربط Profile وHistory وDashboard بالبيانات.
- 21 اختبارًا آليًا للنقاط الأساسية والمصادقة وترحيلات قاعدة البيانات ورفع AB1 والتحليل المبدئي والربط البحثي والمراجعات.

لم يُنفّذ بعد نموذج مصنّف ومتحقق منه لإصدار نتيجة Positive/Negative أو PDF Report. لذلك تبقى `v617f_detected` فارغة. قرار Specialist Review يقيّم الأدلة المتاحة ويحفظها في سجل المراجعة، لكنه لا يحوّلها تلقائيًا إلى نتيجة طفرة.

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

صفحات المصادقة والتحليل والسجل ولوحة المعلومات والملف الشخصي مرتبطة حاليًا بالـ API المحلي.

## قاعدة البيانات

المسار الافتراضي لملف SQLite:

```text
backend/data/geneglass.db
```

يمكن تغييره من `.env`:

```dotenv
DATABASE_PATH=data/geneglass.db
```

تدار بنية قاعدة البيانات بواسطة Alembic. يشغّل التطبيق `upgrade head` عند البدء، ويمكن تشغيله يدويًا:

```powershell
python -m app.db.init_db
```

أو باستخدام Alembic مباشرة:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

عند أول تشغيل على قاعدة GeneGlass قديمة مطابقة للبنية الحالية، يفحص النظام الجداول والأعمدة ثم ينشئ baseline stamp من دون حذف البيانات. إذا كانت القاعدة قديمة جزئيًا أو ناقصة، يوقف التشغيل بدل تعديلها بصمت، ويجب أخذ نسخة احتياطية وإنشاء migration صريح لها.

بعد تعديل SQLAlchemy models مستقبلًا:

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
```

يجب مراجعة migration المولّد قبل تطبيقه.

الجداول الحالية:

- `alembic_version`: رقم migration المطبق حاليًا.
- `users`: بيانات الحساب الأساسية، الدور، حالة الحساب وhash كلمة المرور.
- `analyses`: ملف AB1 المرتبط بالمستخدم، حالة المعالجة، JAK2/V617F، حالة الجودة والنتيجة المستقبلية.
- `reviews`: قرار المراجع وتعليقه وربطه بالتحليل والمستخدم المراجع.
- `candidate_variants`: اختلافات JAK2 البحثية المرشحة.
- `external_annotations`: نتائج ClinVar المخزنة مؤقتًا.

لا توجد بيانات Seed افتراضية؛ لذلك تبدأ الجداول فارغة.

## رفع AB1 والتحليل المبدئي

المسارات الحالية:

- `POST /api/analyses`: رفع ملف AB1 وتشغيل QC وتخزين الأدلة المبدئية.
- `GET /api/analyses`: History مع البحث والفلاتر والصفحات.
- `GET /api/analyses/{id}`: معلومات التحليل المحفوظ.
- `GET /api/analyses/{id}/chromatogram`: الإشارات الأصلية A/C/G/T.
- `GET /api/analyses/{id}/jak2-target`: محاذاة JAK2 وموضع الهدف والقِمم وأسباب المراجعة.
- `GET /api/analyses/{id}/reviews`: سجل قرارات المراجعة الكامل، الأحدث أولًا.
- `POST /api/analyses/{id}/reviews`: إضافة قرار مراجعة جديد مع تعليق، من دون استبدال السجل السابق أو تغيير نتيجة V617F.
- `GET /api/analyses/{id}/research-variants`: المتغيرات البحثية المحفوظة ونتائج المصادر الخارجية المخزنة مؤقتًا.
- `POST /api/analyses/{id}/research-variants/refresh`: استخراج SNV candidates من الجزء المغطى والبحث الاختياري في ClinVar.
- `GET /api/dashboard/summary`: إحصاءات المستخدم من قاعدة البيانات.

التحليل الحالي **مبدئي وغير تشخيصي**. يحدد موضع `NM_004972.4:c.1849G>T` ويعرض جودة الإشارة، لكنه لا يصنف الطفرة قبل اعتماد قواعد قرار واختبارها بملفات مرجعية معلومة النتيجة.

## Extended Research Screening وClinVar

من صفحة Analysis Details يستطيع المختص الضغط على `Search ClinVar`. يقوم النظام حينها بما يلي:

1. يعيد محاذاة base calls الأصلية مع `NM_004972.4` في الاتجاهين.
2. يستخرج اختلافات SNV الصريحة داخل الجزء المغطى فقط.
3. يضع الاختلافات منخفضة الجودة في `Needs Review` ولا يرسلها إلى ClinVar.
4. يرسل وصف HGVS فقط إلى NCBI E-utilities؛ لا يرسل ملف AB1 أو اسم الملف أو معرف المستخدم أو تسلسل العينة الكامل.
5. يحفظ ملخص التصنيفات والحالات المرتبطة وحالة المراجعة ورابط السجل لمدة 24 ساعة افتراضيًا.
6. يعرض فقط المتغيرات التي أعاد ClinVar لها تطابقًا دقيقًا، مع رابط السجل المطابق. المرشحات `not_found` أو `Needs Review` تبقى داخلية ولا تظهر كنتائج خارجية. عند القراءة العكسية تعرض النتيجة المطابقة تغير AB1 الخام والمتمم المرجعي لتجنب الخلط بين C وG أو A وT.

الميزة للاستخدام البحثي فقط. لا تُفسر `No matching record` على أنها `Benign`، ولا يُستخدم تطابق ClinVar لإصدار تشخيص. الإصدار الحالي لا يستخرج indels ولا يحوّل القمم الثانوية المختلطة إلى variants، ولا يستطيع فحص مناطق خارج قراءة Sanger.

إعدادات NCBI الاختيارية في `.env`:

```dotenv
NCBI_TOOL=GeneGlass
NCBI_EMAIL=developer@example.org
NCBI_API_KEY=
CLINVAR_CACHE_HOURS=24
```

استخدم بريد مطور فعليًا مسجلًا مع NCBI عند التشغيل المستمر، ولا ترفع API key إلى Git. يلتزم العميل بحد أقصى يقارب 3 طلبات/ثانية دون مفتاح و10 طلبات/ثانية مع مفتاح، ويحدد كل تحليل بحد أقصى 20 lookup في العملية الواحدة.

ملفات المستخدمين تحفظ محليًا تحت `backend/uploads/`، وهذا المسار مستبعد من Git لمنع رفع بيانات التسلسل أو metadata الخاصة بالعينة.

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
├── migrations/       # Alembic revisions and migration environment
├── app/
│   ├── api/          # HTTP routes
│   ├── cli/          # Interactive user administration
│   ├── core/         # Environment configuration
│   ├── db/           # SQLite engine, sessions, and initialization
│   ├── models/       # Users, analyses, and reviews
│   ├── schemas/      # Request/response schemas
│   ├── services/     # Auth, AB1 parsing, QC, storage, and target mapping
│   └── main.py       # FastAPI application entry point
├── tests/
├── alembic.ini
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```
