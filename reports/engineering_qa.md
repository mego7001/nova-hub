# Engineering Brain QA

Generated at: 2026-02-07T00:19:33.644138Z
Summary: 5 passed / 0 failed

## Tests
- [PASS] Material selection: selected=Aluminum 6061
- [PASS] Slenderness warning: findings=[{'check_id': 'SLENDERNESS_WARNING', 'severity': 'CRITICAL', 'title': 'نحافة عالية', 'detail': 'الشكل طويل ورفيع؛ في احتمال انبعاج تحت الحمل.', 'recommendation': 'قلّل الطول أو زوّد القطر أو أضف دعامات.', 'evidence': [{'path': 'chat', 'line': None, 'excerpt': 'عمود قطره 20 وطوله 1500 شايل 200 كيلو'}], 'assumptions_used': ['geometry'], 'confidence': 0.7}, {'check_id': 'SUPPORT_UNCLEAR', 'severity': 'WARN', 'title': 'الدعم غير واضح', 'detail': 'تم ذكر أحمال بدون تحديد نوع الدعم.', 'recommendation': 'حدّد هل التثبيت ثابت ولا مفصلي ولا مسند.', 'evidence': [], 'assumptions_used': ['supports'], 'confidence': 0.8}]
- [PASS] Tolerance warning: findings=[{'check_id': 'TOLERANCE_TOO_TIGHT', 'severity': 'WARN', 'title': 'تلرانس ضيق جدًا', 'detail': 'التلرانس المطلوب (0.01 مم) أصغر من الحد الأدنى المتوقع للعملية (0.10 مم).', 'recommendation': 'خفّف التلرانس أو حدّد عملية أدق.', 'evidence': [{'path': 'chat', 'line': None, 'excerpt': 'تلرانس ±0.01 على قطعة مطبوعة 3D'}], 'assumptions_used': ['tolerance', 'process'], 'confidence': 0.7}]
- [PASS] Missing supports question: question=الدعم هيكون ثابت ولا مفصلي ولا مسند؟
- [PASS] Redaction: secrets redacted

## Limitations
- QA uses offline extraction; UI panel not exercised.