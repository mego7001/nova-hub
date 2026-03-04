from __future__ import annotations

from typing import Dict, List, Optional

from core.security.secrets import SecretsManager


def build_response(state: Dict, findings: List[Dict], risk: Dict, question: str | None = None) -> str:
    parts = state.get("parts") or []
    material = (state.get("materials", {}) or {}).get("selected_material") or ""
    loads = state.get("loads") or []
    tolerances = state.get("tolerances") or []
    environment = (state.get("context", {}) or {}).get("environment") or ""

    lines: List[str] = []
    ack = "فاهم المطلوب بشكل مبدئي."
    risk_high = risk.get("risk_posture") == "HIGH"
    if risk_high:
        ack = "أنا مختلف مع الاختيار الحالي عشان فيه مخاطرة واضحة."
    lines.append(ack)

    understood = []
    if parts:
        understood.append("تجميعة/قطعة أساسية")
    if material:
        understood.append(f"خامة: {material}")
    if loads:
        understood.append(f"أحمال: {len(loads)} حالة")
    if tolerances:
        understood.append(f"تلرانسات: {len(tolerances)}")
    if environment:
        understood.append(f"بيئة: {environment}")
    if understood:
        lines.append("اللي فهمته: " + "، ".join(understood))

    if findings:
        lines.append("المخاطر المبدئية:")
        for f in findings[:5]:
            sev = f.get("severity", "WARN")
            lines.append(f"- [{sev}] {f.get('detail')}")

    if risk_high:
        lines.append("مقترح بديل: زوّد المقطع أو قلّل الطول أو أضف دعم واضح.")
        lines.append("تحب نعدّل في الاتجاه ده؟")
    else:
        if question:
            lines.append(question)
        else:
            missing = (state.get("assumptions") or {}).get("missing_fields") or []
            if missing:
                lines.append("في معلومات ناقصة. تحب نحدّدها دلوقتي؟")

    lines.append("اقتراح عملي: ثبّت الافتراضات الأساسية قبل أي قرار نهائي.")
    lines.append("تنبيه: ده تصور هندسي مبدئي، مش حساب نهائي.")
    return SecretsManager.redact_text("\n".join(lines))


def build_report(state: Dict, findings: List[Dict], risk: Dict) -> str:
    lines: List[str] = []
    lines.append("# Engineering Brain Report")
    lines.append("")
    lines.append(f"Risk Posture: {risk.get('risk_posture')} (score={risk.get('risk_score'):.2f})")
    lines.append("")
    lines.append("## Summary")
    lines.append(build_response(state, findings, risk, question=None))
    lines.append("")
    lines.append("## Model")
    lines.append(_dump_section(state))
    lines.append("")
    lines.append("## Findings")
    if not findings:
        lines.append("- No findings.")
    else:
        for f in findings:
            lines.append(f"- [{f.get('severity')}] {f.get('title')}: {f.get('detail')}")
            if f.get("recommendation"):
                lines.append(f"  Recommendation: {f.get('recommendation')}")
    lines.append("")
    lines.append("## Notes")
    lines.append("هذا تقرير مبدئي للتوجيه فقط وليس اعتماد هندسي نهائي.")
    return SecretsManager.redact_text("\n".join(lines))


def _dump_section(state: Dict) -> str:
    import json
    try:
        return "```json\n" + json.dumps(state, indent=2, ensure_ascii=False) + "\n```"
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return "(unavailable)"
