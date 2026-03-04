from __future__ import annotations

import zipfile
from pathlib import Path

from core.ingest.unzip import safe_extract_zip
from core.ingest.zip_policy import default_zip_policy


def test_unzip_policy_reasons_are_deterministic(tmp_path: Path):
    z = tmp_path / "mixed.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../evil.txt", b"x")
        zf.writestr("nested.zip", b"fake")
        zf.writestr("tool.exe", b"fake")

    _extracted, rejected = safe_extract_zip(str(z), str(tmp_path / "out"), policy=default_zip_policy())
    codes = sorted(str(item.get("reason_code") or "") for item in rejected if isinstance(item, dict))

    assert codes == ["invalid_member_path", "nested_zip_not_allowed", "unsupported_extension"]
