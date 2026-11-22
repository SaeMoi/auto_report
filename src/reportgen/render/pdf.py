"""DOCX → PDF. LibreOffice(soffice --headless)로 변환함. 설치 경로는 config/settings.yaml output.libreoffice."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

MAC_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def find_soffice(configured: str | None) -> str | None:
    for c in (configured, "soffice", "libreoffice", MAC_PATH):
        if not c:
            continue
        if Path(c).is_file():
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


def convert(docx_path: Path, out_dir: Path, soffice: str | None = None, timeout: int = 180) -> Path:
    exe = find_soffice(soffice)
    if not exe:
        raise RuntimeError("LibreOffice(soffice)를 찾지 못함. 설치하거나 config/settings.yaml output.libreoffice에 경로를 적으세요")
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
                          capture_output=True, text=True, timeout=timeout)
    pdf = out_dir / (docx_path.stem + ".pdf")
    if proc.returncode != 0 or not pdf.exists():
        raise RuntimeError(f"PDF 변환 실패: {proc.stderr.strip() or proc.stdout.strip()}")
    return pdf
