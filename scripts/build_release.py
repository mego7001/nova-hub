from __future__ import annotations

from pathlib import Path
import fnmatch
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import __version__


EXCLUDE_PATTERNS = (
    ".git/*",
    ".venv/*",
    "__pycache__/*",
    "*.pyc",
    ".env",
    ".env.*",
    "tmp_*/*",
    "tmp_pytest/*",
    "tmp_pytest_work/*",
    "workspace/*",
    "logs/*",
    "outputs/*",
    "releases/*",
)


def _is_excluded(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel, pattern):
            return True
    return False


def build_release_zip() -> Path:
    root = ROOT
    releases_dir = root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    out = releases_dir / f"nova_hub_{__version__}.zip"

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if _is_excluded(rel):
                continue
            zf.write(path, rel)
    return out


def main() -> int:
    out = build_release_zip()
    print(f"release_zip: {out}")
    print(f"size_bytes: {out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
