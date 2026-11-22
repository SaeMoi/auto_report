"""2026-11-17 리뷰 반영: 보고서별 canonical, 표지 빈 쪽, 지표 칸 폭, 열 최소 폭."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document

from reportgen import cli
from reportgen.render import docx as D

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_per_report(tmp_path: Path):
    subprocess.run([sys.executable, str(ROOT / "samples" / "make_demo.py")], check=True, capture_output=True)
    shutil.copytree(ROOT / "samples" / "demo" / "input", tmp_path / "input")
    p = str(tmp_path)
    for r in ("diag", "blue"):   # 블루를 나중에 prepare해도 진단 보고서는 결과 보고서 P1(대체 행)을 씀
        assert cli.main(["prepare", p, "-r", r]) == 0
        cli.main(["ai", p, "-r", r, "-a", "fake"])
        cli.main(["approve", p, "-r", r, "--all"])
    assert cli.main(["render", p, "-r", "diag", "--formats", "md"]) == 0
    md = next((tmp_path / "output").glob("diag_v*.md")).read_text(encoding="utf-8")
    assert "블루팀" not in md.splitlines()[0]
    # 보고서별 파일이 없고 공용 파일이 다른 보고서 것이면 멈춤
    (tmp_path / "work" / "diag" / "canonical.json").unlink()
    try:
        cli.main(["render", p, "-r", "diag", "--formats", "md"])
        raise AssertionError("멈춰야 함")
    except SystemExit as e:
        assert "prepare -r diag" in str(e)


def test_cover_note_in_grid(tmp_path: Path):
    md = "# 데모 보고서\n\n| 항목 | 내용 |\n| --- | --- |\n| 문서 버전 | v1.0 |\n| 보안 등급 | 대외비 |\n\n## 1. 요약\n\n본문\n"
    out = D.convert(md, tmp_path / "a.docx", base_dir=tmp_path, reference=ROOT / "templates" / "reference.docx")
    doc = Document(str(out))
    # 보안 등급 줄은 따로 띄운 틀(framePr)이 아니라 표지 격자 표 안에 있음
    assert not doc.element.body.xpath(".//w:framePr")
    assert "대외비" in doc.tables[0].rows[-1].cells[0].text


def test_stat_widths_fit_one_line():
    w, size = D._stat_widths(["30.8 → 69.2%", "1.6 → 3.0", "8건", "0초"], 17)
    assert abs(sum(w) - D.T.CONTENT_WIDTH_CM) < 0.01
    assert w[0] >= D._text_cm("30.8 → 69.2%", size) + 0.6 and size == 17


def test_id_column_not_squeezed():
    doc = Document()
    rows = [["V-ID", "취약점명", "취약점 유형 (OWASP)", "대상", "건수", "위험도", "조치 구분", "시나리오 사용"]]
    rows += [["V-02", "취약한 구성요소 사용 (React2Shell) 긴 이름 " * 2, "A03", "A-01, A-03", "1", "Critical", "-", "-"]] * 5
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    D._widths(t, rows, len(rows[0]), total_cm=D.T.CONTENT_WIDTH_CM)
    w0 = t._tbl.tblGrid.gridCol_lst[0].w.cm
    assert w0 >= 0.2 * 4 + 0.6 - 0.01
