from pathlib import Path
import re


def test_commandbar_has_single_send_handlers():
    path = Path(__file__).resolve().parents[1] / "ui" / "hud_qml" / "qml" / "components" / "CommandBar.qml"
    text = path.read_text(encoding="utf-8")

    assert len(re.findall(r"\bonAccepted\s*:", text)) == 1
    assert text.count("onAccepted: root.triggerSend()") == 1
    assert text.count("onClicked: root.triggerSend()") == 1
    assert text.count('text: "Send"') == 1

    assert text.count('text: "Attach"') == 1
    assert text.count("onClicked: root.attachRequested()") == 1
    assert text.count('text: "Tools"') == 1
    assert text.count("onClicked: root.toolsRequested()") == 1

    assert "signal taskModeChangedRequested(string modeId)" in text
    assert "taskModeCombo" in text
