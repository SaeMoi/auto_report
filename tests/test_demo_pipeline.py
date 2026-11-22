"""시연 데이터로 prepare → ai(fake) → check → approve → render 전체를 돌려 봄."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from reportgen import cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def demo(tmp_path_factory) -> Path:
    subprocess.run([sys.executable, str(ROOT / "samples" / "make_demo.py")], check=True, capture_output=True)
    dst = tmp_path_factory.mktemp("proj") / "demo"
    shutil.copytree(ROOT / "samples" / "demo" / "input", dst / "input")
    return dst


@pytest.mark.parametrize("report", ["plan", "diag", "pentest", "blue"])
def test_pipeline(demo: Path, report: str):
    p = str(demo)
    assert cli.main(["prepare", p, "-r", report]) == 0
    work = demo / "work" / report
    tasks = [json.loads(x) for x in (work / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if x]
    assert tasks, "AI 작업이 하나 이상 있어야 함"
    # 마스킹 안 된 값·입력 폴더 경로가 지시문에 들어가지 않음
    for t in tasks:
        assert str(demo / "input") not in t["prompt"]
    assert cli.main(["ai", p, "-r", report, "-a", "fake"]) == 0
    assert cli.main(["check", p, "-r", report]) == 0
    # 확정 전에는 최종본을 만들지 않음
    assert cli.main(["render", p, "-r", report, "--formats", "md"]) == 1
    assert cli.main(["approve", p, "-r", report, "--all"]) == 0
    assert cli.main(["render", p, "-r", report, "--formats", "md,docx"]) == 0
    md = next((demo / "output").glob(f"{report}_v*.md")).read_text(encoding="utf-8")
    assert "[AI 작업 대기]" not in md
    assert next((demo / "output").glob(f"{report}_v*.docx")).stat().st_size > 10_000


def test_diag_content(demo: Path):
    cli.main(["prepare", str(demo), "-r", "diag"])
    data = json.loads((demo / "build" / "canonical.json").read_text(encoding="utf-8"))
    f = {x["finding_id"]: x for x in data["findings"]}
    assert f["V-01"]["severity"] == "high"          # 대표 건(최고 등급) 기준
    assert f["V-01"]["representative_id"] == "V-01-1"
    assert f["V-03"]["severity"] == "critical"
    assert [p["patch_id"] for p in data["patches"]] == ["P-01", "P-02"]
    rep = next(i for i in data["instances"] if i["instance_id"] == "V-01-1")
    assert rep["poc"]["result_facts"] == ["회원 이메일 152건이 상품 목록 자리에 나타남"]   # 캡션 제외
    ev = [e["evidence_id"] for e in data["evidence"]]
    assert ev == sorted(ev) and ev[0] == "E-001"


def test_locked_text_survives(demo: Path):
    p = str(demo)
    cli.main(["prepare", p, "-r", "diag"])
    work = demo / "work" / "diag"
    (work / "locked.yaml").write_text("4-1:summary.overall: 사람이 고친 총평임(V-01)\n", encoding="utf-8")
    cli.main(["ai", p, "-r", "diag", "-a", "fake", "--redo"])
    cli.main(["check", p, "-r", "diag"])
    data = json.loads((work / "report.json").read_text(encoding="utf-8"))
    assert data["summary_overall"] == "사람이 고친 총평임(V-01)"


def test_result_report_removed(demo: Path):
    """2026-11-22 옛 한 권짜리 결과 보고서(-r result)는 없앰. 노션 P1 「결과 보고서」 행은 diag·pentest가 대신 씀."""
    with pytest.raises(SystemExit):
        cli.main(["prepare", str(demo), "-r", "result"])
    assert not (ROOT / "templates" / "result.md.j2").exists()
    for r in ("diag", "pentest"):
        cli.main(["prepare", str(demo), "-r", r])
        issues = json.loads((demo / "work" / r / "intake_issues.json").read_text(encoding="utf-8"))
        assert any("결과 보고서" in i.get("msg", "") for i in issues), r   # 대체 행 사용 경고
