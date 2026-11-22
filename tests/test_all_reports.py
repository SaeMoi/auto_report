"""-r 없이(=all) 돌리면 진단·모의해킹·블루 세 권이 따로 나옴(2026-11-21)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from reportgen import cli

ROOT = Path(__file__).resolve().parents[1]


def test_all_makes_three_books(tmp_path: Path):
    subprocess.run([sys.executable, str(ROOT / "samples" / "make_demo.py")], check=True, capture_output=True)
    shutil.copytree(ROOT / "samples" / "demo" / "input", tmp_path / "demo" / "input")
    p = str(tmp_path / "demo")
    assert cli.main(["prepare", p]) == 0
    assert cli.main(["ai", p, "-a", "fake"]) == 0
    assert cli.main(["approve", p, "--all"]) == 0
    assert cli.main(["render", p, "--formats", "md"]) == 0
    out = tmp_path / "demo" / "output"
    for r in ("diag", "pentest", "blue"):
        assert list(out.glob(f"{r}_v*.md")), r
    assert not list(out.glob("result_v*.md"))
    diag = next(out.glob("diag_v*.md")).read_text(encoding="utf-8")
    assert "공격 내러티브" not in diag and "ATT&CK 한눈에 보기" not in diag   # 진단에 모의해킹이 붙지 않음
