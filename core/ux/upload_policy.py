from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from core.ingest.file_types import classify_path


class UploadTarget(str, Enum):
    GENERAL = "general"
    PROJECT = "project"


@dataclass(frozen=True)
class UploadLimits:
    max_files: int
    max_total_bytes: int
    ttl_days: int


@dataclass(frozen=True)
class UploadRejection:
    path: str
    reason: str


@dataclass(frozen=True)
class UploadAcceptance:
    path: str
    file_type: str
    size_bytes: int


@dataclass(frozen=True)
class UploadPolicyResult:
    target: str
    accepted: Tuple[UploadAcceptance, ...]
    rejected: Tuple[UploadRejection, ...]
    limits: UploadLimits
    existing_files: int
    existing_bytes: int
    projected_files: int
    projected_bytes: int

    @property
    def ok(self) -> bool:
        return len(self.accepted) > 0 and len(self.rejected) == 0

    @property
    def accepted_paths(self) -> List[str]:
        return [item.path for item in self.accepted]


def default_upload_limits(target: UploadTarget | str) -> UploadLimits:
    if isinstance(target, UploadTarget):
        normalized = target.value
    else:
        normalized = str(target or "").strip().lower()
    if normalized == UploadTarget.PROJECT.value:
        return UploadLimits(max_files=200, max_total_bytes=2 * 1024 * 1024 * 1024, ttl_days=0)
    return UploadLimits(max_files=25, max_total_bytes=150 * 1024 * 1024, ttl_days=14)


def _normalize_target(target: UploadTarget | str) -> UploadTarget:
    if isinstance(target, UploadTarget):
        return target
    text = str(target or "").strip().lower()
    if text == UploadTarget.PROJECT.value:
        return UploadTarget.PROJECT
    return UploadTarget.GENERAL


def _normalize_paths(paths: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for raw in paths:
        p = str(raw or "").strip()
        if not p:
            continue
        absolute = os.path.abspath(p)
        key = absolute.lower() if os.name == "nt" else absolute
        if key in seen:
            continue
        seen.add(key)
        out.append(absolute)
    return out


def _path_rejection(path: str, reason: str) -> UploadRejection:
    return UploadRejection(path=str(path), reason=str(reason))


def scan_storage_usage(root: str) -> Dict[str, int]:
    files = 0
    total_bytes = 0
    root_path = Path(root)
    if not root_path.exists():
        return {"files": 0, "bytes": 0}
    for fp in root_path.rglob("*"):
        if not fp.is_file():
            continue
        files += 1
        try:
            total_bytes += int(fp.stat().st_size)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            continue
    return {"files": files, "bytes": total_bytes}


def evaluate_upload_batch(
    paths: Sequence[str],
    *,
    target: UploadTarget | str,
    existing_files: int = 0,
    existing_bytes: int = 0,
) -> UploadPolicyResult:
    normalized_target = _normalize_target(target)
    limits = default_upload_limits(normalized_target)
    accepted: List[UploadAcceptance] = []
    rejected: List[UploadRejection] = []

    projected_files = max(0, int(existing_files))
    projected_bytes = max(0, int(existing_bytes))

    for path in _normalize_paths(paths):
        if not os.path.exists(path):
            rejected.append(_path_rejection(path, "File was not found."))
            continue
        if os.path.isdir(path):
            rejected.append(_path_rejection(path, "Directories are not supported. Select files only."))
            continue

        file_type = classify_path(path)
        if file_type == "binary":
            rejected.append(
                _path_rejection(
                    path,
                    "Unsupported format. Allowed: zip/pdf/docx/xlsx/images/txt/code/config files.",
                )
            )
            continue

        try:
            size_bytes = int(os.path.getsize(path))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            rejected.append(_path_rejection(path, "Could not read file size."))
            continue

        if projected_files + 1 > limits.max_files:
            rejected.append(
                _path_rejection(
                    path,
                    f"Quota exceeded: max {limits.max_files} files for {normalized_target.value} memory.",
                )
            )
            continue
        if projected_bytes + size_bytes > limits.max_total_bytes:
            limit_mb = limits.max_total_bytes / (1024.0 * 1024.0)
            rejected.append(
                _path_rejection(
                    path,
                    f"Quota exceeded: max {limit_mb:.0f} MB for {normalized_target.value} memory.",
                )
            )
            continue

        accepted.append(UploadAcceptance(path=path, file_type=file_type, size_bytes=size_bytes))
        projected_files += 1
        projected_bytes += size_bytes

    return UploadPolicyResult(
        target=normalized_target.value,
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        limits=limits,
        existing_files=max(0, int(existing_files)),
        existing_bytes=max(0, int(existing_bytes)),
        projected_files=projected_files,
        projected_bytes=projected_bytes,
    )


def split_paths_by_policy(
    paths: Iterable[str],
    *,
    target: UploadTarget | str,
    existing_files: int = 0,
    existing_bytes: int = 0,
) -> Tuple[List[str], List[UploadRejection]]:
    result = evaluate_upload_batch(
        list(paths),
        target=target,
        existing_files=existing_files,
        existing_bytes=existing_bytes,
    )
    return result.accepted_paths, list(result.rejected)
