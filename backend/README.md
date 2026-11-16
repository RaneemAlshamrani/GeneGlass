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
- مسار Specialist Review لحفظ النتيجة النهائية `Not Detected` أو `Heterozygous` أو `Homozygous` أو `Inconclusive`، مع تعليق وسجل زمني كامل.
- Audit Trail للعمليات المهمة مع المستخدم المنفذ والوقت، من دون حفظ كلمات المرور أو التوكنات أو محتوى AB1، مع إمكانية طباعة السجل من صفحة تفاصيل التحليل.
- مسار سريع لإنشاء Molecular Report بعد حفظ نتيجة المختص في Specialist Review: بيانات المريض، ملف Normal Control AB1 خاص بالحالة، ثم PDF من صفحتين.
- يتم اتخاذ قرار Specialist Review وإنشاء التقرير من صفحة `New Analysis` نفسها. تعرض `History` و`Analysis Details` التقرير المعتمد للتحميل فقط؛ وإذا لم يُحفظ القرار أو لم يُنشأ التقرير، تعيد المستخدم إلى التحليل لإكماله.
- صفحة PDF الأولى تعرض قرار المختص فقط، والصفحة الثانية تعرض كروماتوجرام العينة والـNormal Control من الإشارات الأصلية؛ لا تُدرج نتيجة المودل أو احتمالاته في التقرير.
- حفظ الأدلة المبدئية في SQLite وربط Profile وHistory وDashboard بالبيانات.
- اختبارات آلية للنقاط الأساسية والمصادقة وترحيلات قاعدة البيانات ورفع AB1 والتحليل المبدئي والمراجعات والتقارير وسجل التدقيق والتحقق التقني.

المودل الحالي بحثي وغير متحقق منه سريريًا. لذلك لا يُستخدم كقرار التقرير ولا يُدرج في ملف PDF. يسجل المختص النتيجة داخل Specialist Review، ويستخدمها التقرير تلقائيًا مع إمكانية تعديل نص التفسير قبل الاعتماد. لا يسمح الـAPI بإنشاء تقرير قبل حفظ إحدى نتائج المختص الأربع.

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
- `audit_events`: سجل غير قابل للتعديل عبر الـAPI للعمليات المهمة والمستخدم المنفذ والتحليل المرتبط إن وجد.
- `model_predictions`: سجل append-only لكل تشغيل للمودل، مع الاحتمالات وTree SHAP explanation وبصمة ملف المودل وإصدار مشتق من حزمة المودل والمعالجة وحالة QC وقت التشغيل.
- `molecular_reports`: مسودات وإصدارات التقارير المعتمدة، وقرار المختص، ومسار Normal Control الخاص بكل تقرير.

لا توجد بيانات Seed افتراضية؛ لذلك تبدأ الجداول فارغة.

## رفع AB1 والتحليل المبدئي

المسارات الحالية:

- `POST /api/analyses`: رفع ملف AB1 وتشغيل QC وتخزين الأدلة المبدئية.
- `GET /api/analyses`: History مع البحث والفلاتر والصفحات.
- `GET /api/analyses/{id}`: معلومات التحليل المحفوظ.
- `GET /api/analyses/{id}/chromatogram`: الإشارات الأصلية A/C/G/T.
- `GET /api/analyses/{id}/jak2-target`: محاذاة JAK2 وموضع الهدف والقِمم وأسباب المراجعة.
- `GET /api/analyses/{id}/ai-prediction`: آخر نتيجة محفوظة للمودل الحالي، ويُنشئ سجلًا عند عدم وجود نتيجة متوافقة مع إصدار المودل وحالة QC.
- `POST /api/analyses/{id}/ai-prediction/refresh`: تشغيل المودل من جديد وإضافة سجل جديد من دون حذف النتائج السابقة.
- `GET /api/analyses/{id}/reviews`: سجل قرارات المراجعة الكامل، الأحدث أولًا.
- `POST /api/analyses/{id}/reviews`: إضافة نتيجة `Not Detected` أو `Heterozygous` أو `Homozygous` أو `Inconclusive` مع تعليق، من دون استبدال السجل السابق.
- `GET /api/analyses/{id}/report`: جلب أحدث مسودة أو إصدار للتقرير.
- `PUT /api/analyses/{id}/report`: حفظ البيانات ورفع Normal Control AB1؛ تعديل تقرير معتمد ينشئ إصدارًا جديدًا ولا يغيّر الإصدار السابق.
- `POST /api/analyses/{id}/report/finalize`: اعتماد قرار المختص بعد التحقق من توفر كروماتوجرام العينة والـNormal Control.
- `GET /api/analyses/{id}/report.pdf`: إنشاء وتنزيل الإصدار المعتمد من PDF من دون بيانات المودل.
- `GET /api/analyses/{id}/audit-events`: سجل التدقيق المقيد بمالك التحليل.
- `GET /api/audit-events`: أحدث عمليات المستخدم وعمليات تحليلاته، بحد أقصى 200 سجل.
- `GET /api/dashboard/summary`: إحصاءات المستخدم من قاعدة البيانات.

التحليل والمودلات الحالية **للبحث ودعم المراجعة فقط وليست للتشخيص**. نتيجة مودل الطفرة الثنائية `negative/hetero` لا تدعم `homo` كفئة، ولا تستخدم Noise كتنبؤ جيني. الاحتمالات المعروضة ليست ثقة سريرية. تعرض History وDashboard أحدث نتيجة طفرة محفوظة فقط، بينما تبقى كل عمليات التشغيل السابقة في `model_predictions` وسجل التدقيق.

بعد إضافة ميزة الحفظ إلى قاعدة بيانات تحتوي تحليلات سابقة، شغّل مرة واحدة:

```powershell
.\.venv\Scripts\python.exe -m app.cli.backfill_model_predictions
```

الأمر لا يستبدل نتيجة سابقة متوافقة مع نفس بصمة المودل وحالة QC.

## تفسير المودل باستخدام Tree SHAP

يعرض New Analysis وAnalysis Details تفسيرًا قابلًا للفتح أسفل نتيجة المودل. يوضح التفسير مساهمة كل واحدة من الخصائص السبع في احتمال `hetero`. القيم موجبة باتجاه Hetero وسالبة باتجاه Negative، ومجموعها مع `base_value` يعيد احتمال Hetero نفسه ضمن سماحية عددية صغيرة.

الملف `ai_assets/shap_background.json` مبني من 101 ملفًا في training split فقط، ولا يحتوي أسماء ملفات AB1 أو مساراتها. تم التحقق بالـSHA-256 أن ملفات الاختبار العشرين لا تتقاطع مع الخلفية. لأن manifest التدريب الأصلي من Colab لم يُحفظ، تحمل الخلفية ملاحظة صريحة بأن التقسيم الحالي reconstructed training complement وليس إثباتًا مستقلًا للتقسيم الأصلي.

لإعادة بناء الخلفية من النسخة المحلية للداتا:

```powershell
.\.venv\Scripts\python.exe -m app.cli.build_shap_background `
  --training-root "C:\path\to\GeneGlass_Final_Training_AB1" `
  --testing-root "C:\path\to\GeneGlass_Final_Testing_AB1"
```

SHAP يفسر سلوك المودل فقط، ولا يثبت السببية البيولوجية أو الصحة السريرية. الخصائص المشتقة والمترابطة مثل `reference_peak` و`alternative_peak` و`alternative_ratio` و`peak_overlap_score` قد تتشارك الإسناد. لا يُضاف تفسير SHAP إلى Molecular PDF، الذي يبقى مبنيًا على قرار المختص.

## Reference Dataset and Pipeline Validation

توجد أداة offline للتحقق القابل لإعادة التشغيل في `app.cli.validate_pipeline`. تستخدم manifest منزوع الهوية، وتحفظ SHA-256 للـmanifest ومرجع المحاذاة الجينومي `NC_000009.12` ومرجع التسمية `NM_004972.4` وكل ملف AB1، ولا تضع المسار المحلي أو التسلسل الخام داخل التقرير.

```powershell
.\.venv\Scripts\python.exe -m app.cli.validate_pipeline `
  --manifest validation/private/reference_manifest.csv `
  --output validation/reports/validation-2026-11-05.json
```

القالب والتعليمات التفصيلية داخل `validation/`. البيانات والتقارير الفعلية مستبعدة من Git. الأداة تقيس نجاح القراءة، محاذاة الهدف، الهوية، التغطية، Phred وتوفر القمم، لكنها تضع classification metrics في `not_calculated` لأن النظام لا يملك classifier متحققًا منه ولا reference labels مستقلة كافية.

كشف التشغيل الأول أن محاذاة genomic DNA مع transcript-only reference كانت تغطي 19.66–20.00% فقط. بعد تثبيت نافذة GRCh38 `NC_000009.12:5073170-5074370` وإبقاء `NM_004972.4` لتحويل HGVS، أعيد تشغيل التحقق بتاريخ 2026-11-05: تمت معالجة 5/5 ملفات، ونجحت 5/5 في technical checks، بهوية 98.44–99.78% وتغطية 96.41–99.79%. هذه الملفات ما زالت موسومة `unknown` وليست مجموعة تحقق موجبة/سالبة، لذلك classification metrics تظل `not_calculated`.

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
├── validation/       # Manifest template and private validation workflow
├── app/
│   ├── api/          # HTTP routes
│   ├── cli/          # Interactive user administration
│   ├── core/         # Environment configuration
│   ├── db/           # SQLite engine, sessions, and initialization
│   ├── models/       # Users, analyses, and reviews
│   ├── schemas/      # Request/response schemas
│   ├── services/     # Auth, AB1 parsing, QC, storage, and target mapping
│   ├── validation/   # Reference dataset validation and report generation
│   └── main.py       # FastAPI application entry point
├── tests/
├── alembic.ini
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```
