from __future__ import annotations
import os
import zipfile
from pathlib import PurePosixPath
from typing import Dict, List, Tuple

from core.ingest.zip_policy import ZipPolicy, default_zip_policy, rejection


class ZipLimitError(ValueError):
    pass


def _safe_member_parts(member: str) -> List[str]:
    raw = str(member or "").replace("\\", "/").strip()
    if not raw:
        return []
    norm = PurePosixPath(raw)
    return [str(part) for part in norm.parts]


def _is_invalid_member_path(member: str) -> bool:
    raw = str(member or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/"):
        return True
    parts = _safe_member_parts(raw)
    if not parts:
        return True
    if any(part in ("", ".", "..") for part in parts):
        return True
    return False


def safe_extract_zip(zip_path: str, dest: str, policy: ZipPolicy | None = None) -> Tuple[List[str], List[Dict[str, str]]]:
    active = policy or default_zip_policy()
    if not os.path.isfile(zip_path):
        raise FileNotFoundError("Zip file not found")
    extracted: List[str] = []
    rejections: List[Dict[str, str]] = []
    total = 0
    abs_dest = os.path.abspath(dest)
    os.makedirs(abs_dest, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        if len(infos) > int(active.max_files):
            raise ZipLimitError(f"too_many_files: max_files={active.max_files}")
        for info in infos:
            member = str(info.filename or "")
            if _is_invalid_member_path(member):
                rejections.append(
                    rejection(
                        member,
                        "Invalid member path in zip archive.",
                        "invalid_member_path",
                    )
                )
                continue
            target = os.path.abspath(os.path.join(abs_dest, member))
            if not target.startswith(abs_dest + os.sep):
                rejections.append(
                    rejection(
                        member,
                        "zip-slip blocked by extraction policy.",
                        "zip_slip_blocked",
                    )
                )
                continue
            if member.endswith("/"):
                os.makedirs(target, exist_ok=True)
                continue
            ext = os.path.splitext(member)[1].lower()
            if ext == ".zip" and not bool(active.allow_nested_zip):
                rejections.append(
                    rejection(
                        member,
                        "Nested zip is not allowed by policy.",
                        "nested_zip_not_allowed",
                    )
                )
                continue
            if ext and active.allowed_extensions and ext not in active.allowed_extensions:
                rejections.append(
                    rejection(
                        member,
                        f"Unsupported extension '{ext}' inside zip.",
                        "unsupported_extension",
                    )
                )
                continue
            size = int(info.file_size or 0)
            if size > int(active.max_member_bytes):
                rejections.append(
                    rejection(
                        member,
                        f"Member exceeds max_member_bytes={active.max_member_bytes}.",
                        "member_too_large",
                    )
                )
                continue
            if total + size > int(active.max_total_uncompressed_bytes):
                rejections.append(
                    rejection(
                        member,
                        f"Archive exceeds max_total_uncompressed_bytes={active.max_total_uncompressed_bytes}.",
                        "max_total_bytes_exceeded",
                    )
                )
                break
            total += size
            os.makedirs(os.path.dirname(target), exist_ok=True)
            written = 0
            with zf.open(info) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1024 * 64)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > int(active.max_member_bytes):
                        rejections.append(
                            rejection(
                                member,
                                f"Member exceeds max_member_bytes={active.max_member_bytes} while streaming.",
                                "member_too_large",
                            )
                        )
                        break
                    out.write(chunk)
            if written > int(active.max_member_bytes):
                try:
                    os.remove(target)
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
                continue
            extracted.append(target)
    return extracted, rejections
