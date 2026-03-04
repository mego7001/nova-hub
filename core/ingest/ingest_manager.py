from __future__ import annotations

import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor

from core.ingest.file_types import classify_path
from core.ingest.index_store import IndexStore
from core.ingest.parsers.docx_parser import parse_docx
from core.ingest.parsers.image_parser import parse_image
from core.ingest.parsers.pdf_parser import parse_pdf
from core.ingest.parsers.pptx_parser import parse_pptx
from core.ingest.parsers.text_parser import parse_text
from core.ingest.parsers.xlsx_parser import parse_xlsx
from core.ingest.unzip import ZipLimitError, safe_extract_zip
from core.memory.migration import load_manifest, merge_records_lossless, save_manifest
from core.projects.manager import ProjectManager
from core.security.api_importer import ApiImporter
from core.security.secrets import SecretsManager
from core.tooling.invoker import InvokeContext, invoke_tool
from core.ux.upload_policy import UploadTarget, default_upload_limits, evaluate_upload_batch, scan_storage_usage


@dataclass(frozen=True)
class IngestScope:
    target: str
    scope_id: str
    root: str
    docs_root: str
    extracted_root: str
    index_path: str


class IngestManager:
    def __init__(self, workspace_root: Optional[str] = None, runner=None, registry=None):
        self.manager = ProjectManager(workspace_root)
        self.workspace_root = os.path.abspath(self.manager.workspace_root)
        self.runner = runner
        self.registry = registry
        self.secrets = SecretsManager(workspace_root=self.workspace_root)
        self.cleanup_general_storage()

    def ingest(self, project_id: str, paths: List[str]) -> Dict[str, Any]:
        # Backward-compatible project ingest entrypoint.
        return self.ingest_project(project_id, paths)

    def ingest_project(self, project_id: str, paths: List[str]) -> Dict[str, Any]:
        if not project_id:
            raise ValueError("project_id required")
        proj = self.manager.get_project_paths(project_id)
        scope = IngestScope(
            target=UploadTarget.PROJECT.value,
            scope_id=str(project_id),
            root=str(proj.project_root),
            docs_root=os.path.join(proj.project_root, "docs"),
            extracted_root=os.path.join(proj.project_root, "extracted"),
            index_path=os.path.join(proj.project_root, "index.json"),
        )
        return self._ingest_scope(scope, paths)

    def ingest_general(self, chat_id: str, paths: List[str]) -> Dict[str, Any]:
        cid = self._normalize_chat_id(chat_id)
        scope_root = self._general_scope_root(cid)
        scope = IngestScope(
            target=UploadTarget.GENERAL.value,
            scope_id=cid,
            root=scope_root,
            docs_root=os.path.join(scope_root, "docs"),
            extracted_root=os.path.join(scope_root, "extracted"),
            index_path=os.path.join(scope_root, "index.json"),
        )
        cleanup = self.cleanup_general_storage()
        result = self._ingest_scope(scope, paths)
        result["ttl_cleanup"] = cleanup
        # Run cleanup after ingest too, so stale sessions are pruned opportunistically.
        result["ttl_cleanup_after"] = self.cleanup_general_storage()
        return result

    def migrate_general_to_project(
        self,
        chat_id: str,
        project_id: str,
        *,
        remove_source: bool = True,
    ) -> Dict[str, Any]:
        cid = self._normalize_chat_id(chat_id)
        source_root = self._general_scope_root(cid)
        docs_src = os.path.join(source_root, "docs")
        extracted_src = os.path.join(source_root, "extracted")
        index_src = os.path.join(source_root, "index.json")
        proj = self.manager.get_project_paths(project_id)
        manifest_dir = os.path.join(proj.project_root, "migrations")
        manifest_path = os.path.join(manifest_dir, f"general_{cid}.json")
        manifest = load_manifest(manifest_path)
        if not os.path.exists(source_root):
            if manifest:
                return {
                    "status": "already_migrated",
                    "chat_id": cid,
                    "project_id": project_id,
                    "migrated_docs": int(manifest.get("migrated_docs") or 0),
                    "migrated_records": int(manifest.get("migrated_records") or 0),
                    "manifest_path": manifest_path,
                }
            return {"status": "no_data", "chat_id": cid, "project_id": project_id, "migrated_docs": 0, "migrated_records": 0}

        docs_dst_root = os.path.join(proj.project_root, "docs")
        extracted_dst_root = os.path.join(proj.project_root, "extracted")
        index_dst = os.path.join(proj.project_root, "index.json")
        os.makedirs(docs_dst_root, exist_ok=True)
        os.makedirs(extracted_dst_root, exist_ok=True)

        docs_dst = os.path.join(docs_dst_root, f"general_{cid}")
        extracted_dst = os.path.join(extracted_dst_root, f"general_{cid}")
        os.makedirs(docs_dst, exist_ok=True)
        os.makedirs(extracted_dst, exist_ok=True)

        path_map: Dict[str, str] = {}
        migrated_docs = self._copy_tree_with_map(docs_src, docs_dst, path_map)
        migrated_extracted = self._copy_tree_with_map(extracted_src, extracted_dst, path_map)

        src_records = IndexStore(index_src).load() if os.path.exists(index_src) else []
        dst_index = IndexStore(index_dst)
        dst_records = dst_index.load()
        merged_records, migrated_records = merge_records_lossless(
            dst_records,
            src_records,
            chat_id=cid,
            path_map=path_map,
        )
        dst_index.save(merged_records, writer=self._write_text, repo_root=proj.project_root)
        save_manifest(
            manifest_path,
            {
                "status": "ok",
                "chat_id": cid,
                "project_id": project_id,
                "migrated_docs": migrated_docs,
                "migrated_extracted_files": migrated_extracted,
                "migrated_records": migrated_records,
                "source_removed": bool(remove_source),
                "project_index_path": index_dst,
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

        if remove_source:
            shutil.rmtree(source_root, ignore_errors=True)

        return {
            "status": "ok",
            "chat_id": cid,
            "project_id": project_id,
            "migrated_docs": migrated_docs,
            "migrated_extracted_files": migrated_extracted,
            "migrated_records": migrated_records,
            "source_removed": bool(remove_source),
            "project_index_path": index_dst,
            "manifest_path": manifest_path,
        }

    def cleanup_general_storage(self) -> Dict[str, int]:
        sessions_root = Path(self.workspace_root) / "chat" / "sessions"
        ttl_days = int(default_upload_limits(UploadTarget.GENERAL).ttl_days)
        cutoff = time.time() - (ttl_days * 24 * 60 * 60)
        removed_sessions = 0
        removed_files = 0

        if not sessions_root.exists():
            return {"removed_sessions": 0, "removed_files": 0}

        for child in sessions_root.iterdir():
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            latest = self._latest_mtime(child)
            if latest >= cutoff:
                continue
            removed_files += self._count_files(child)
            shutil.rmtree(child, ignore_errors=True)
            removed_sessions += 1
        return {"removed_sessions": removed_sessions, "removed_files": removed_files}

    def _ingest_scope(self, scope: IngestScope, paths: List[str]) -> Dict[str, Any]:
        if not paths:
            return {
                "status": "no_files",
                "target": scope.target,
                "scope_id": scope.scope_id,
                "accepted": [],
                "rejected": [],
                "counts": {"files_ingested": 0, "files_extracted": 0, "keys_imported": 0, "rejected": 0},
                "errors": [],
            }

        os.makedirs(scope.docs_root, exist_ok=True)
        os.makedirs(scope.extracted_root, exist_ok=True)
        os.makedirs(os.path.dirname(scope.index_path), exist_ok=True)

        docs_usage = scan_storage_usage(scope.docs_root)
        policy_result = evaluate_upload_batch(
            paths,
            target=scope.target,
            existing_files=int(docs_usage.get("files") or 0),
            existing_bytes=int(docs_usage.get("bytes") or 0),
        )

        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        batch_dir = os.path.join(scope.docs_root, batch_id)
        os.makedirs(batch_dir, exist_ok=True)

        index = IndexStore(scope.index_path)
        records = index.load()
        errors: List[str] = []
        accepted_rows: List[Dict[str, Any]] = []
        rejected_rows: List[Dict[str, str]] = [{"path": item.path, "reason": item.reason, "reason_code": "policy_rejected"} for item in policy_result.rejected]
        ingested = 0
        extracted_count = 0
        imported_keys = 0

        api_importer = ApiImporter(self.secrets, runner=self.runner, registry=self.registry)

        def process_item(item):
            src = str(item.path)
            base = os.path.basename(src)
            dest = os.path.join(batch_dir, base)
            try:
                self._copy_file(src, dest)
            except (OSError, shutil.Error) as exc:
                return None, {"path": src, "reason": f"copy failed: {exc}", "reason_code": "copy_failed"}, None

            file_type = classify_path(dest)
            record = self._base_record(dest, file_type)

            accepted_item: Dict[str, Any] = {
                "path": src,
                "stored_path": dest,
                "type": file_type,
                "size": int(item.size_bytes),
                "doc_id": record["doc_id"],
                "extracted_text_path": "",
                "ocr_status": "n/a",
                "index_status": "pending",
                "source_zip": "",
                "zip_member": "",
            }

            if file_type == "zip":
                unzip_dir = os.path.join(batch_dir, "unzipped")
                os.makedirs(unzip_dir, exist_ok=True)
                z_recs: List[Dict[str, Any]] = []
                z_errors: List[str] = []
                zip_rejected: List[Dict[str, str]] = []
                accepted_items: List[Dict[str, Any]] = [accepted_item]
                try:
                    extracted_paths, unzip_errors = safe_extract_zip(dest, unzip_dir)
                    for err in unzip_errors:
                        if isinstance(err, dict):
                            zip_rejected.append(
                                {
                                    "path": str(err.get("path") or src),
                                    "reason": str(err.get("reason") or "zip policy rejected member"),
                                    "reason_code": str(err.get("reason_code") or "zip_policy_rejected"),
                                }
                            )
                        else:
                            z_errors.append(str(err))
                    for up in extracted_paths:
                        up_type = classify_path(up)
                        rec = self._base_record(up, up_type)
                        rec["source_zip"] = dest
                        rec["zip_member"] = os.path.relpath(up, unzip_dir).replace("\\", "/")
                        z_recs.append(rec)
                        self._parse_and_store(rec, scope.extracted_root)
                        accepted_items.append(
                            {
                                "path": src,
                                "stored_path": up,
                                "type": up_type,
                                "size": int(rec.get("size") or 0),
                                "doc_id": str(rec.get("doc_id") or ""),
                                "extracted_text_path": str(rec.get("extracted_text_path") or ""),
                                "ocr_status": str((rec.get("metadata") or {}).get("ocr_status") or "n/a"),
                                "index_status": "indexed",
                                "source_zip": dest,
                                "zip_member": str(rec.get("zip_member") or ""),
                            }
                        )
                except (ZipLimitError, OSError, ValueError, RuntimeError) as exc:
                    zip_rejected.append(
                        {
                            "path": src,
                            "reason": f"zip error: {exc}",
                            "reason_code": "zip_policy_rejected",
                        }
                    )
                accepted_item["index_status"] = "indexed"
                return record, None, (accepted_items, z_recs, z_errors, zip_rejected)

            _, parse_err = self._parse_and_store(record, scope.extracted_root)
            accepted_item["extracted_text_path"] = str(record.get("extracted_text_path") or "")
            accepted_item["ocr_status"] = str((record.get("metadata") or {}).get("ocr_status") or "n/a")
            accepted_item["index_status"] = "indexed"
            
            # API import (sequential for now as it modifies shared state self.secrets)
            if base.lower() == "api.txt" or file_type == "text":
                try:
                    content = parse_text(dest).get("text", "")
                    detected = api_importer.detect_keys(content)
                    if base.lower() == "api.txt" or len(detected) >= 2:
                        api_importer.import_from_text(content)
                except (OSError, UnicodeDecodeError, ValueError, RuntimeError):
                    pass

            return record, None, ([accepted_item], [], [parse_err] if parse_err else [], [])

        with ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 4) * 4)) as pool:
            results = list(pool.map(process_item, policy_result.accepted))

        for rec, rej, extra in results:
            if rej:
                rejected_rows.append(rej)
                continue
            if rec:
                records.append(rec)
                acc_items, z_recs, z_errs, zip_rejected = extra
                accepted_rows.extend([x for x in acc_items if isinstance(x, dict)])
                records.extend(z_recs)
                errors.extend(z_errs)
                rejected_rows.extend([x for x in zip_rejected if isinstance(x, dict)])
                ingested += len([x for x in acc_items if isinstance(x, dict)])
                extracted_count += sum(1 for r in z_recs if r.get("extracted_text_path"))
                if rec.get("extracted_text_path"):
                    extracted_count += 1

        index.save(records, writer=self._write_text_direct, repo_root=scope.root if scope.target == UploadTarget.PROJECT.value else None)
        status = "ok" if not rejected_rows and not errors else "partial"

        return {
            "status": status,
            "target": scope.target,
            "scope_id": scope.scope_id,
            "batch_id": batch_id,
            "docs_dir": batch_dir,
            "extracted_dir": scope.extracted_root,
            "index_path": scope.index_path,
            "accepted": accepted_rows,
            "rejected": rejected_rows,
            "counts": {
                "files_ingested": ingested,
                "files_extracted": extracted_count,
                "keys_imported": imported_keys,
                "rejected": len(rejected_rows),
            },
            "errors": errors,
        }

    def _base_record(self, path: str, ftype: str) -> Dict[str, Any]:
        stat = os.stat(path)
        return {
            "doc_id": uuid.uuid4().hex[:12],
            "stored_path": path,
            "type": ftype,
            "size": stat.st_size,
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def _parse_and_store(self, record: Dict[str, Any], extracted_root: str) -> Tuple[int, str]:
        ftype = str(record.get("type") or "")
        path = str(record.get("stored_path") or "")
        if not path or ftype in ("zip", "binary"):
            record["extracted_text_path"] = ""
            return 0, ""

        result: Dict[str, Any] = {}
        if ftype == "text":
            result = parse_text(path)
        elif ftype == "pdf":
            result = parse_pdf(path)
        elif ftype == "docx":
            result = parse_docx(path)
        elif ftype == "xlsx":
            result = parse_xlsx(path)
        elif ftype == "pptx":
            result = parse_pptx(path)
        elif ftype == "image":
            result = parse_image(path)

        record["metadata"] = {k: v for k, v in result.items() if k not in ("text",)}
        text = str(result.get("text") or "")
        if text:
            out_path = os.path.join(extracted_root, f"{record['doc_id']}.txt")
            self._write_text_direct(out_path, text)
            record["extracted_text_path"] = out_path
            return 1, ""

        record["extracted_text_path"] = ""
        parse_error = str(result.get("error") or "").strip()
        if parse_error:
            record["metadata"]["error"] = parse_error
            return 0, f"{os.path.basename(path)} parse error: {parse_error}"
        return 0, ""

    def _copy_file(self, src: str, dest: str) -> None:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)

    def _write_text(self, path: str, text: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tool = self.registry.tools.get("fs.write_text") if self.registry else None
        if tool and self.runner:
            invoke_tool(
                "fs.write_text",
                {"path": path, "text": text, "target": path},
                InvokeContext(runner=self.runner, registry=self.registry, mode=""),
            )
            return
        self._write_text_direct(path, text)

    def _write_text_direct(self, path: str, text: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _normalize_chat_id(self, chat_id: str) -> str:
        raw = str(chat_id or "").strip().lower()
        if not raw:
            return "general"
        safe = re.sub(r"[^a-z0-9_.-]+", "_", raw)
        safe = safe.strip("._-")
        if not safe:
            safe = "general"
        return safe[:96]

    def _general_scope_root(self, chat_id: str) -> str:
        return os.path.join(self.workspace_root, "chat", "sessions", self._normalize_chat_id(chat_id))

    @staticmethod
    def _latest_mtime(root: Path) -> float:
        latest = 0.0
        try:
            latest = max(latest, float(root.stat().st_mtime))
        except OSError:
            pass
        for child in root.rglob("*"):
            try:
                latest = max(latest, float(child.stat().st_mtime))
            except OSError:
                continue
        return latest

    @staticmethod
    def _count_files(root: Path) -> int:
        count = 0
        for child in root.rglob("*"):
            if child.is_file():
                count += 1
        return count

    @staticmethod
    def _copy_tree_with_map(src_root: str, dst_root: str, path_map: Dict[str, str]) -> int:
        if not os.path.exists(src_root):
            return 0
        copied = 0
        for base, _dirs, files in os.walk(src_root):
            rel = os.path.relpath(base, src_root)
            target_base = dst_root if rel == "." else os.path.join(dst_root, rel)
            os.makedirs(target_base, exist_ok=True)
            for name in files:
                src_path = os.path.join(base, name)
                dst_path = os.path.join(target_base, name)
                shutil.copy2(src_path, dst_path)
                path_map[src_path] = dst_path
                copied += 1
        return copied

