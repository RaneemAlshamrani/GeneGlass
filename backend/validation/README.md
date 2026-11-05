# Reference Dataset Validation

هذه الأداة تبني evidence report قابلًا لإعادة التشغيل لخط GeneGlass المبدئي. لا تعلن أن النظام متحقق سريريًا ولا تحسب sensitivity أو specificity لأن الإصدار الحالي لا يصدر تصنيف Positive/Negative متحققًا منه.

## تجهيز البيانات الخاصة

1. انسخ `reference_manifest.example.csv` إلى `validation/private/reference_manifest.csv`.
2. ضع ملفات AB1 المرجعية داخل `validation/private/data/` أو استخدم مسارات محلية مطلقة.
3. استخدم `sample_id` منزوع الهوية فقط. لا تضع اسم المريض أو رقم الملف الطبي أو تاريخ الميلاد.
4. القيم المسموحة لـ `expected_v617f_status`: `positive`, `negative`, `unknown`.
5. أي label موجبة أو سالبة تتطلب `comparator_method` مستقلة عن GeneGlass، مثل اختبار مختبري مؤكد أو reference material موثق.
6. القيم المسموحة لـ `source_type`: `commercial_reference_material`, `proficiency_testing`, `previously_tested_specimen`, `synthetic_control`, `development_sample`.
7. استخدم `replicate_group` لربط التكرارات التقنية لنفس المادة من دون كشف هوية العينة.

المجلدان `validation/private/` و`validation/reports/` مستبعدان من Git.

## التشغيل

من داخل `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.cli.validate_pipeline `
  --manifest validation/private/reference_manifest.csv `
  --output validation/reports/validation-2026-11-05.json
```

الأداة ترفض استبدال تقرير موجود، وتحفظ في التقرير SHA-256 للـmanifest والمرجع وكل ملف AB1 حتى يمكن كشف تغير مدخلات التشغيل. التقرير لا يحتوي المسار المحلي أو التسلسل الخام.

## ما يتم قياسه حاليًا

- نجاح قراءة AB1.
- العثور على موضع JAK2 V617F داخل المحاذاة.
- اتجاه القراءة.
- هوية المحاذاة ونسبة تغطية القراءة.
- توفر Phred عند الهدف.
- توفر القمم والمنطقة المحيطة بالهدف.
- أسباب `Needs Review`.

هذه technical checks وليست clinical accuracy. عند توفر classifier مثبت وعينات مرجعية مستقلة يمكن إضافة PPA/NPA واتفاق النتائج في مرحلة لاحقة.
