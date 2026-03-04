from __future__ import annotations

from typing import Tuple


_DISALLOWED = [
    "certify",
    "certification",
    "stamp",
    "approval",
    "code compliance",
    "final design",
    "fea",
    "ansys",
    "abaqus",
    "توقيع",
    "اعتماد",
    "ختم",
    "شهادة",
    "مطابقة كود",
    "تصميم نهائي",
    "تحليل عناصر محددة",
    "محاكاة نهائية",
]


def check_limits(text: str) -> Tuple[bool, str]:
    low = (text or "").lower()
    for k in _DISALLOWED:
        if k in low:
            return True, "ده تصور هندسي مبدئي، مش اعتماد نهائي ولا بديل عن حسابات معتمدة."
    return False, ""
