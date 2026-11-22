"""2026-11-18 결과 보고서를 진단(diag)·모의해킹(pentest)으로 나눈 뒤의 확인."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from reportgen import cli, refdata
from reportgen.intake.mapping import to_kst
from reportgen.render.pentest_ctx import attack_strip

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def demo(tmp_path_factory) -> Path:
    subprocess.run([sys.executable, str(ROOT / "samples" / "make_demo.py")], check=True, capture_output=True)
    dst = tmp_path_factory.mktemp("proj") / "demo"
    shutil.copytree(ROOT / "samples" / "demo" / "input", dst / "input")
    return dst


def test_to_kst():
    assert to_kst("2026-11-13T13:37:00.000Z") == "2026-11-13T22:37:00+09:00"     # 노션 API(UTC)
    assert to_kst("November 13, 2026 10:37 PM") == "2026-11-13T22:37:00+09:00"   # CSV 내보내기
    assert to_kst("2026-11-13 22:37") == "2026-11-13T22:37:00+09:00"
    assert to_kst("2026-11-11") == "2026-11-11"
    assert to_kst("November 11, 2026") == "2026-11-11"
    assert to_kst("2026-11-15T14:32:00.000Z → 2026-11-15T14:38:00.000Z") == "2026-11-15T23:32:00+09:00"
    assert to_kst("모름") == ""


def test_attack_tactic():
    assert refdata.attack_tactic("T1059.004 Command and Scripting Interpreter: Unix Shell [검증 요]")["ko"] == "실행"
    assert refdata.attack_tactic("T1053.003")["ko"] == "지속성"
    assert refdata.attack_tactic("T9999", "Initial Access")["ko"] == "초기 접근"
    assert refdata.attack_tactic("모름") is None
    strip = attack_strip([
        {"step_id": "S1-STEP1", "attack_technique": "T1595.002", "result": {"status": "success"}},
        {"step_id": "S1-STEP2", "attack_technique": "T1190", "result": {"status": "success"}},
        {"step_id": "S1-STEP3", "attack_technique": "T1190", "result": {"status": "failed"}},
        {"step_id": "S1-STEP4", "attack_technique": "T1565.001", "result": {"status": "untested"}}])
    assert [c["tactic"] for c in strip] == ["정찰", "초기 접근", "영향"]
    assert strip[1]["steps_label"] == "STEP2~3" and strip[1]["status"] == "success"
    assert strip[2]["status"] == "untested"


def test_diag_has_no_scenarios(demo: Path):
    p = str(demo)
    assert cli.main(["prepare", p, "-r", "diag"]) == 0
    tasks = (demo / "work" / "diag" / "tasks.jsonl").read_text(encoding="utf-8")
    assert "scenario_step" not in tasks and '"S1-STEP' not in tasks
    cli.main(["ai", p, "-r", "diag", "-a", "fake"])
    cli.main(["render", p, "-r", "diag", "--draft", "--formats", "md"])
    md = next((demo / "output").glob("diag_v*_draft.md")).read_text(encoding="utf-8")
    assert "취약점 진단 보고서" in md.splitlines()[0]
    assert "시나리오 사용" not in md and "Part B" not in md and "공격 내러티브" not in md
    assert "## 6. 취약점 보안 대책" in md and "## 8. 부록" in md


def test_pentest_content(demo: Path):
    p = str(demo)
    assert cli.main(["prepare", p, "-r", "pentest"]) == 0
    own = demo / "work" / "pentest" / "canonical.json"   # 보고서별 사본이 없는 버전은 build/ 것을 씀
    data = json.loads((own if own.exists() else demo / "build" / "canonical.json").read_text(encoding="utf-8"))
    steps = {s["step_id"]: s for s in data["scenarios"][0]["steps"]}
    assert steps["S1-STEP1"]["result"]["status"] == "success"      # 「확인」
    assert steps["S1-STEP2"]["result"]["status"] == "success"      # 옛 선택지 「성공」
    assert steps["S1-STEP5"]["result"]["status"] == "untested"
    assert steps["S1-STEP1"]["time_basis"] == "log"
    assert any(seg.get("evidence_id") for seg in steps["S1-STEP1"]["flow"])   # 수행 내용 안 그림
    assert not any("UNION 요청 화면" in (seg.get("text") or "") for seg in steps["S1-STEP1"]["flow"])   # 캡션은 글로 안 나옴
    sc = data["scenarios"][0]
    assert sc["cleanup"] and sc["pitfalls"] and sc["causes"] and sc["clues"]
    cli.main(["ai", p, "-r", "pentest", "-a", "fake"])
    cli.main(["render", p, "-r", "pentest", "--draft", "--formats", "md,docx"])
    md = next((demo / "output").glob("pentest_v*_draft.md")).read_text(encoding="utf-8")
    assert "모의해킹 보고서" in md.splitlines()[0]
    assert "ATT&CK 한눈에 보기" in md and "| 전술 | 초기 접근 | 영향 |" in md
    assert "## 3. 시나리오 S1" in md and "경로 차단 권고" in md and "정리 내역" in md
    assert "V-01-1 | SQL 인젝션" in md   # 2-4 사용한 취약점
