from pathlib import Path

from core.ux.upload_policy import UploadTarget, evaluate_upload_batch, scan_storage_usage


def _write(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_upload_policy_accepts_supported_and_rejects_unsupported(tmp_path: Path):
    ok_file = _write(tmp_path / "notes.txt", "hello")
    bad_file = _write(tmp_path / "archive.bin", "xxxx")

    result = evaluate_upload_batch([ok_file, bad_file], target=UploadTarget.GENERAL)

    assert len(result.accepted) == 1
    assert result.accepted[0].path == ok_file
    assert len(result.rejected) == 1
    assert "Unsupported format" in result.rejected[0].reason


def test_upload_policy_enforces_general_quota(tmp_path: Path):
    paths = []
    for i in range(3):
        paths.append(_write(tmp_path / f"f_{i}.txt", "a"))

    result = evaluate_upload_batch(
        paths,
        target=UploadTarget.GENERAL,
        existing_files=24,
        existing_bytes=0,
    )
    assert len(result.accepted) == 1
    assert len(result.rejected) == 2
    assert "Quota exceeded" in result.rejected[0].reason


def test_upload_policy_project_has_larger_budget(tmp_path: Path):
    file_a = _write(tmp_path / "a.txt", "a" * 1024)
    file_b = _write(tmp_path / "b.txt", "b" * 1024)

    result = evaluate_upload_batch(
        [file_a, file_b],
        target=UploadTarget.PROJECT,
        existing_files=199,
        existing_bytes=(2 * 1024),
    )
    assert len(result.accepted) == 1
    assert len(result.rejected) == 1


def test_scan_storage_usage_counts_files_and_bytes(tmp_path: Path):
    _write(tmp_path / "docs" / "x.txt", "abcd")
    _write(tmp_path / "docs" / "y.txt", "ef")
    usage = scan_storage_usage(str(tmp_path / "docs"))
    assert usage["files"] == 2
    assert usage["bytes"] >= 6
