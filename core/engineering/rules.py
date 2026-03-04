from __future__ import annotations

from typing import Dict, List

from core.engineering import tolerances as tol


def evaluate(state: Dict, signals: Dict) -> List[Dict]:
    findings: List[Dict] = []
    geometry = signals.get("geometry") or {}
    loads = state.get("loads") or []
    supports = state.get("supports") or []
    tolerances = state.get("tolerances") or []
    env = (state.get("context", {}).get("environment") or "").lower()
    material = (state.get("materials", {}).get("selected_material") or "").lower()

    # 1) Slenderness warning
    if geometry.get("height") and geometry.get("diameter") and loads:
        ratio = float(geometry["height"]) / float(geometry["diameter"])
        if ratio > 20:
            findings.append(_finding(
                "SLENDERNESS_WARNING",
                "CRITICAL" if ratio > 30 else "WARN",
                "نحافة عالية",
                "الشكل طويل ورفيع؛ في احتمال انبعاج تحت الحمل.",
                "قلّل الطول أو زوّد القطر أو أضف دعامات.",
                [signals.get("geometry_evidence")],
                ["geometry"],
                0.7,
            ))

    # 2) Material mismatch
    if "corrosive" in env or "outdoor" in env:
        if "steel" in material and "stainless" not in material:
            findings.append(_finding(
                "MATERIAL_MISMATCH",
                "WARN",
                "خامة غير مناسبة للبيئة",
                "البيئة قد تكون مسببة للتآكل وخامة الحديد العادي معرضة للتلف.",
                "فكّر في Stainless 304 أو ألمنيوم مع حماية.",
                [signals.get("environment_evidence")],
                ["environment", "material"],
                0.6,
            ))

    # 3) Safety factor low
    safety = state.get("safety", {})
    if float(safety.get("safety_factor_target", 2.0)) < 1.5 and loads:
        findings.append(_finding(
            "SAFETY_FACTOR_LOW",
            "WARN",
            "عامل أمان منخفض",
            "عامل الأمان المقترح منخفض بالنسبة للأحمال المذكورة.",
            "ارفع عامل الأمان أو زوّد المقطع.",
            [],
            ["safety_factor"],
            0.6,
        ))

    # 4) Tolerance too tight
    process = signals.get("process") or ""
    if tolerances:
        cap = tol.process_capability(process)
        for t in tolerances:
            tol_plus = t.get("tol_plus")
            tol_minus = t.get("tol_minus")
            if tol_plus is None and isinstance(t.get("tolerance"), dict):
                tol_plus = t["tolerance"].get("plus", 0)
                tol_minus = t["tolerance"].get("minus", 0)
            tol_val = min(abs(float(tol_plus or 0)), abs(float(tol_minus or 0)))
            if tol_val > 0 and tol_val < cap:
                findings.append(_finding(
                    "TOLERANCE_TOO_TIGHT",
                    "WARN",
                    "تلرانس ضيق جدًا",
                    f"التلرانس المطلوب ({tol_val:.2f} مم) أصغر من الحد الأدنى المتوقع للعملية ({cap:.2f} مم).",
                    "خفّف التلرانس أو حدّد عملية أدق.",
                    [signals.get("tolerance_evidence")],
                    ["tolerance", "process"],
                    0.7,
                ))
                break

    # 5) Support unclear
    if loads and not supports:
        findings.append(_finding(
            "SUPPORT_UNCLEAR",
            "WARN",
            "الدعم غير واضح",
            "تم ذكر أحمال بدون تحديد نوع الدعم.",
            "حدّد هل التثبيت ثابت ولا مفصلي ولا مسند.",
            [],
            ["supports"],
            0.8,
        ))

    # 6) Thermal expansion risk
    if signals.get("delta_t") and geometry.get("length"):
        delta_t = float(signals.get("delta_t"))
        length = float(geometry.get("length"))
        if delta_t >= 40 and length >= 500:
            findings.append(_finding(
                "THERMAL_EXPANSION_RISK",
                "WARN",
                "تغير حراري ملحوظ",
                "فرق الحرارة كبير وطول القطعة طويل؛ ممكن تمدد ملحوظ.",
                "راجع الخلوصات أو أضف سماحات حرارية.",
                [],
                ["temperature"],
                0.6,
            ))

    # 7) Fastener risk
    if signals.get("fastener") and not signals.get("bolt_grade"):
        findings.append(_finding(
            "FASTENER_RISK",
            "WARN",
            "معلومات تثبيت ناقصة",
            "تم ذكر ربط بمسامير بدون تحديد grade أو preload.",
            "حدد نوع المسامير وقيم الشد المبدئية.",
            [],
            ["fastener"],
            0.5,
        ))

    # 8) Weld heat distortion
    if signals.get("welded") and tolerances:
        findings.append(_finding(
            "WELD_HEAT_DISTORTION",
            "WARN",
            "تشوهات حرارة اللحام",
            "اللحام مع تلرانسات ضيقة قد يسبب تشوه.",
            "اترك سماحات أو خطط للتقويم بعد اللحام.",
            [],
            ["weld", "tolerance"],
            0.5,
        ))

    return findings


def next_questions(findings: List[Dict]) -> List[str]:
    questions = []
    for f in findings:
        if f.get("check_id") == "SUPPORT_UNCLEAR":
            questions.append("الدعم هيكون ثابت ولا مفصلي ولا مسند؟")
        if f.get("check_id") == "TOLERANCE_TOO_TIGHT":
            questions.append("عملية التصنيع إيه بالضبط؟ CNC ولا طباعة 3D؟")
        if f.get("check_id") == "MATERIAL_MISMATCH":
            questions.append("القطعة هتشتغل في بيئة رطبة/خارجية؟")
    return questions


def _finding(check_id: str, severity: str, title: str, detail: str, recommendation: str, evidence: List, assumptions_used: List[str], confidence: float) -> Dict:
    ev = [e for e in (evidence or []) if e]
    return {
        "check_id": check_id,
        "severity": severity,
        "title": title,
        "detail": detail,
        "recommendation": recommendation,
        "evidence": ev,
        "assumptions_used": assumptions_used,
        "confidence": confidence,
    }
