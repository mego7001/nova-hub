from __future__ import annotations

import re
from typing import Tuple


_DISALLOWED = [
    "certify",
    "certification",
    "stamp",
    "approval",
    "code compliance",
    "fea",
    "ansys",
    "abaqus",
    "solidworks simulation",
    "final design",
    "manufacturing tolerance",
    "safety approval",
    "كود",
    "اعتماد",
    "ختم",
    "شهادة",
    "تحليل عناصر محددة",
    "fea",
    "محاكاة",
    "اعتماد نهائي",
    "تصنيع نهائي",
    "تفاوتات",
]


def check_limits(text: str) -> Tuple[bool, str]:
    if not text:
        return False, ""
    low = text.lower()
    for k in _DISALLOWED:
        if k in low:
            return True, "ده تصور هندسي مبدئي، مش اعتماد نهائي ولا بديل عن حسابات معتمدة."
    if re.search(r"\b(factor of safety|fos)\b", low):
        return True, "تقدير عامل الأمان يحتاج حسابات مفصلة، واللي هنا مجرد تصور مبدئي."
    return False, ""
