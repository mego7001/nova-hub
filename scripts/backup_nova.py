#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

SNAPSHOT_EXCLUDES = [
    "workspace/runtime/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    ".pytest_cache/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    "*.log",
    "*.sqlite3",
    "*.sqlite3-wal",
    "*.sqlite3-shm",
]


def is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def setup_logger(backup_dir: Path) -> logging.Logger:
    logger = logging.getLogger("nova_hub_backup")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    backup_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(backup_dir / "nova_hub_backup.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def unique_archive_path(backup_dir: Path, base_name: str) -> Path:
    candidate = backup_dir / f"{base_name}.zip"
    if not candidate.exists():
        return candidate

    idx = 1
    while True:
        candidate = backup_dir / f"{base_name}_{idx}.zip"
        if not candidate.exists():
            return candidate
        idx += 1


def normalize_pattern(pattern: str) -> str:
    return pattern.replace("\\", "/").strip()


def build_exclude_patterns(mode: str, user_excludes: list[str] | None) -> list[str]:
    patterns: list[str] = []
    if mode == "snapshot":
        patterns.extend(SNAPSHOT_EXCLUDES)
    if user_excludes:
        patterns.extend(user_excludes)
    # Normalize + dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for p in patterns:
        n = normalize_pattern(p)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def should_exclude(rel_path_posix: str, patterns: list[str]) -> bool:
    rel_path_posix = rel_path_posix.strip("/")
    name = rel_path_posix.rsplit("/", 1)[-1]

    for pattern in patterns:
        p = normalize_pattern(pattern)
        if not p:
            continue

        # Treat "<dir>/**" as excluding that directory and all descendants.
        if p.endswith("/**"):
            prefix = p[:-3].rstrip("/")
            if rel_path_posix == prefix or rel_path_posix.startswith(prefix + "/"):
                return True

        if fnmatch(rel_path_posix, p) or fnmatch(name, p):
            return True

    return False


def write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def create_backup(
    source_dir: Path,
    backup_dir: Path,
    mode: str,
    user_excludes: list[str] | None,
    logger: logging.Logger,
) -> tuple[Path, dict[str, Any]]:
    source_dir = source_dir.resolve()
    backup_dir = backup_dir.resolve()

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source is not a directory: {source_dir}")

    # Prevent recursive/self-including backups.
    if is_subpath(backup_dir, source_dir):
        raise ValueError(
            "Backup directory must be outside the source directory "
            f"(source={source_dir}, backup={backup_dir})"
        )

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    archive_base = f"nova_hub_backup_{timestamp}"
    archive_path = unique_archive_path(backup_dir, archive_base)
    manifest_path = backup_dir / "MANIFEST.json"

    exclude_patterns = build_exclude_patterns(mode, user_excludes)

    manifest: dict[str, Any] = {
        "timestamp": timestamp,
        "source_dir": str(source_dir),
        "mode": mode,
        "python_version": sys.version.replace("\n", " "),
        "exclude_patterns": exclude_patterns,
        "total_files_attempted": 0,
        "files_added": 0,
        "failed_files": [],
        "archive_path": str(archive_path),
    }

    # Requirement: generate manifest before zipping starts.
    write_manifest(manifest_path, manifest)

    logger.info("Starting backup")
    logger.info("Source: %s", source_dir)
    logger.info("Backup dir: %s", backup_dir)
    logger.info("Archive: %s", archive_path)
    logger.info("Mode: %s", mode)
    if exclude_patterns:
        logger.info("Active exclusions: %s", exclude_patterns)

    files_added = 0
    total_attempted = 0
    failed_files: list[dict[str, str]] = []

    with ZipFile(archive_path, mode="w", compression=ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)

            # Prune excluded directories to avoid descending into them.
            kept_dirs: list[str] = []
            for d in dirs:
                rel_dir = (root_path / d).resolve().relative_to(source_dir).as_posix()
                if should_exclude(rel_dir, exclude_patterns):
                    continue
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            for filename in files:
                file_path = root_path / filename
                rel_file = file_path.resolve().relative_to(source_dir).as_posix()

                if should_exclude(rel_file, exclude_patterns):
                    continue

                total_attempted += 1
                try:
                    zf.write(file_path, arcname=rel_file)
                    files_added += 1
                except Exception as exc:
                    err = {"path": rel_file, "error": str(exc)}
                    failed_files.append(err)
                    logger.exception("Failed to add '%s': %s", rel_file, exc)

    manifest["total_files_attempted"] = total_attempted
    manifest["files_added"] = files_added
    manifest["failed_files"] = failed_files
    write_manifest(manifest_path, manifest)

    archive_size = archive_path.stat().st_size if archive_path.exists() else 0
    logger.info(
        "Backup finished. Attempted=%d Added=%d Failed=%d ArchiveBytes=%d",
        total_attempted,
        files_added,
        len(failed_files),
        archive_size,
    )
    logger.info("Manifest written to: %s", manifest_path)

    return archive_path, manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create timestamped zip backups of the Nova Hub project."
    )
    parser.add_argument(
        "--source",
        default=str(Path.cwd()),
        help="Source project directory (default: current working directory).",
    )
    parser.add_argument(
        "--backup-dir",
        required=True,
        help=r"Backup folder for zip + MANIFEST.json (example: D:\nouva hub\backups).",
    )
    parser.add_argument(
        "--mode",
        choices=("snapshot", "full"),
        default="snapshot",
        help="Backup mode: snapshot (default, excludes transient files) or full.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional exclusion pattern (repeatable). Example: --exclude '*.tmp' --exclude 'reports/**'",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    source_dir = Path(args.source).expanduser()
    backup_dir = Path(args.backup_dir).expanduser()
    mode = str(args.mode).strip().lower()

    logger = setup_logger(backup_dir)

    try:
        archive_path, manifest = create_backup(
            source_dir=source_dir,
            backup_dir=backup_dir,
            mode=mode,
            user_excludes=args.exclude,
            logger=logger,
        )
    except Exception as exc:
        logger.exception("Backup failed: %s", exc)
        return 1

    failed_count = len(manifest.get("failed_files", []))
    if failed_count > 0:
        logger.warning(
            "Backup completed with errors. Archive=%s FailedFiles=%d (exit code 2).",
            archive_path,
            failed_count,
        )
        return 2

    logger.info("Backup created successfully: %s", archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())