"""2026-11-21 블루: 팀 와주 페이지에 없는 값은 「팀 기록 없음」, 룰 요약표, 채울 수 없는 칸은 경고."""
from pathlib import Path

from reportgen.intake import check
from reportgen.intake.notion_export import rule_catalog
from reportgen.render.markdown import no_record
from reportgen.validate import output


def test_rule_catalog(tmp_path: Path):
    d = tmp_path / "blue"
    d.mkdir()
    (d / "탐지 규칙 abc.md").write_text(
        "# 탐지 규칙\n\n| Rule ID | 탐지 내용 | Level | 대상 |\n| --- | --- | --- | --- |\n"
        "| <b>100119</b> | Log4Shell 유입 (웹 로그) | 9 | Nginx |\n| 31103 | SQLi | 7 | x |\n\n"
        "```xml\n<rule id=\"100103\" level=\"10\">\n  <description>x</description>\n</rule>\n```\n", encoding="utf-8")
    cat = rule_catalog([d])
    assert cat[100119]["desc"].startswith("Log4Shell") and cat[100119]["level"] == "9"
    assert 31103 not in cat
    assert "<rule id=\"100103\"" in cat[100103]["xml"]


def test_no_record():
    md = ("## 9. 침해사고 분석 (대표 시나리오 S2 [확인 필요])\n구현 :: [확인 필요]\n| D-30 | [확인 필요] |\n"
          "- 예상 오탐: 정상 검색도 걸릴 수 있음 [확인 필요]\n피해 데이터는 [확인 필요: 범위]\n")
    out = no_record(md)
    assert "[확인 필요" not in out
    assert "## 9. 침해사고 분석 (대표 시나리오 S2)" in out
    assert "구현 :: 팀 기록 없음" in out and "| D-30 | 팀 기록 없음 |" in out
    assert "걸릴 수 있음 (팀 기록 없음)" in out


def test_blue_checks_are_warnings():
    data = {"project": {}, "blue": {
        "test_cases": [{"test_id": "D-27", "status": "executed", "outcome": "detected", "score": 4,
                        "alerts": [{"rule_id": 100127}]}],
        "detection_fixes": [{"fix_id": "F-10", "test_ids": ["D-27"], "rule_ids": [100127, 100103],
                             "retest": {"score_after": 4, "outcome_after": "detected"}}],
        "rule_catalog": [{"rule_id": 100127, "desc": "업로드 웹셸", "level": "12"},
                         {"rule_id": 100103, "desc": "반복 로그인 실패", "xml": "<rule id=\"100103\"></rule>"}]}}
    res = output.check_blue(data)
    for code in ("O-04", "O-08"):
        hits = [i for i in res if i["rule"] == code]
        assert hits and all(i["level"] == "warning" for i in hits), code
    refs, have = output.rule_refs(data["blue"])
    assert 100103 in have and 100127 not in have


def test_r20_source_ip_soft():
    i = {"level": "error", "rule": "R-20", "where": "D-30", "msg": "실행 완료인데 「출발지 IP」이 비어 있음"}
    assert check._soften(i)["level"] == "warning"
