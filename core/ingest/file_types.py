from __future__ import annotations
import os
from typing import Optional

TEXT_EXT = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".ini", ".cfg"}
PDF_EXT = {".pdf"}
DOCX_EXT = {".docx"}
XLSX_EXT = {".xlsx"}
PPTX_EXT = {".pptx"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"}
ZIP_EXT = {".zip"}


def classify_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in ZIP_EXT:
        return "zip"
    if ext in PDF_EXT:
        return "pdf"
    if ext in DOCX_EXT:
        return "docx"
    if ext in XLSX_EXT:
        return "xlsx"
    if ext in PPTX_EXT:
        return "pptx"
    if ext in IMAGE_EXT:
        return "image"
    if ext in TEXT_EXT:
        return "text"
    return "binary"


def guess_mime(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if ext == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if ext == ".pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if ext in IMAGE_EXT:
        return "image"
    if ext in TEXT_EXT:
        return "text/plain"
    if ext == ".zip":
        return "application/zip"
    return None
