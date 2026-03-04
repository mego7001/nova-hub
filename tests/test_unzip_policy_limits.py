from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from core.ingest.unzip import ZipLimitError, safe_extract_zip
from core.ingest.zip_policy import ZipPolicy, default_allowed_extensions


def _build_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_unzip_policy_enforces_max_files(tmp_path: Path):
    z = tmp_path / "many.zip"
    _build_zip(z, {"a.txt": b"a", "b.txt": b"b", "c.txt": b"c"})
    policy = ZipPolicy(
        max_files=2,
        max_total_uncompressed_bytes=50_000_000,
        max_member_bytes=10_000_000,
        allow_nested_zip=False,
        allowed_extensions=frozenset(default_allowed_extensions()),
    )

    with pytest.raises(ZipLimitError):
        safe_extract_zip(str(z), str(tmp_path / "out"), policy=policy)


def test_unzip_policy_enforces_member_size(tmp_path: Path):
    z = tmp_path / "big_member.zip"
    _build_zip(z, {"a.txt": b"0123456789"})
    policy = ZipPolicy(
        max_files=500,
        max_total_uncompressed_bytes=50_000_000,
        max_member_bytes=5,
        allow_nested_zip=False,
        allowed_extensions=frozenset(default_allowed_extensions()),
    )

    extracted, rejected = safe_extract_zip(str(z), str(tmp_path / "out2"), policy=policy)
    assert extracted == []
    assert rejected
    assert rejected[0]["reason_code"] == "member_too_large"
