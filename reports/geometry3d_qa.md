# Geometry3D QA

Generated at: 2026-02-06T20:38:22.765593Z
Summary: 5 passed / 0 failed

## Tests
- [PASS] Simple box: [{'id': 'box_3_8937', 'type': 'box', 'dims': {'x': 100.0, 'y': 80.0, 'z': 60.0}, 'position': {'x': 0.0, 'y': 0.0, 'z': 0.0}, 'material': '', 'support': '', 'load': '', 'hollow': False, 'thickness': 0.0}]
- [PASS] Cylinder dims: [{'id': 'cylinder_2_4445', 'type': 'cylinder', 'dims': {'diameter': 200.0, 'height': 1200.0}, 'position': {'x': 0.0, 'y': 0.0, 'z': 0.0}, 'material': '', 'support': '', 'load': '', 'hollow': False, 'thickness': 1200.0}]
- [PASS] Cantilever warning: warnings=[{'severity': 'WARNING', 'title': 'Slenderness', 'detail': 'الشكل طويل ورفيع؛ في احتمال انبعاج أو اهتزاز.'}, {'severity': 'WARNING', 'title': 'Support', 'detail': 'النموذج كابولي أو غير مدعوم؛ المخاطر عالية بدون تثبيت واضح.'}]
- [PASS] Ambiguous description: confidence=0.0
- [PASS] Arabic+English input: [{'id': 'cylinder_2_9366', 'type': 'cylinder', 'dims': {'diameter': 120.0, 'height': 500.0}, 'position': {'x': 0.0, 'y': 0.0, 'z': 0.0}, 'material': '', 'support': '', 'load': '', 'hollow': False, 'thickness': 0.0}]

## Limitations
- QA uses offline parser only; UI preview not exercised.