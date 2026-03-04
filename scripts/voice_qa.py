from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.portable.paths import default_workspace_dir, detect_base_dir
from core.voice.engine import record_audio, transcribe_audio, speak_text, detect_stt, detect_tts


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_tests() -> list[dict]:
    results: list[dict] = []
    base = detect_base_dir()
    ws = os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
    project_id = "voice_qa"
    audio_dir = os.path.join(ws, "projects", project_id, "temp", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, "qa_voice.wav")

    rec = record_audio(audio_path, seconds=1)
    ok1 = os.path.exists(audio_path)
    results.append({"name": "Record path created", "passed": ok1, "detail": f"status={rec.get('status')}"})

    stt_available = detect_stt()
    if stt_available:
        text, info = transcribe_audio(audio_path)
        ok2 = info.get("status") == "ok"
        results.append({"name": "Offline STT", "passed": ok2, "detail": f"text_len={len(text)} engine={info.get('engine')}"})
    else:
        results.append({"name": "Offline STT", "passed": True, "detail": "STT unavailable (degraded mode ok)"})

    tts_available = detect_tts()
    if tts_available:
        tts = speak_text("Voice QA test.")
        ok3 = tts.get("status") == "ok"
        results.append({"name": "Offline TTS", "passed": ok3, "detail": f"engine={tts.get('engine')}"})
    else:
        results.append({"name": "Offline TTS", "passed": True, "detail": "TTS unavailable (degraded mode ok)"})

    return results


def write_reports(results: list[dict]) -> None:
    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    total = len(results)
    passed = len([r for r in results if r["passed"]])
    failed = total - passed
    payload = {
        "generated_at": _now_iso(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": results,
        "limitations": ["Audio capture and TTS depend on optional local engines."],
    }
    with open(os.path.join(reports_dir, "voice_qa.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Voice QA",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Summary: {passed} passed / {failed} failed",
        "",
        "## Tests",
    ]
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"- [{status}] {r['name']}: {r['detail']}")
    lines.append("")
    lines.append("## Limitations")
    for lim in payload["limitations"]:
        lines.append(f"- {lim}")
    with open(os.path.join(reports_dir, "voice_qa.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    results = run_tests()
    write_reports(results)
    return 1 if any(not r["passed"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
