"""2026-11-21: 날짜만 있는 값은 KST로 읽음(dtutil), 공용 canonical.json이 다른 보고서 것이면 멈춤."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from reportgen import cli
from reportgen.build import merge
from reportgen.config import Project
from reportgen.dtutil import KST, parse_dt
from reportgen.validate import output


def test_parse_dt_kst_and_mixed():
    d = parse_dt("2026-11-13")
    assert d.tzinfo == KST
    assert (parse_dt("2026-11-13T10:00:00+09:00") - d).total_seconds() == 36000
    assert parse_dt("2026-11-13T01:00:00Z").utcoffset().total_seconds() == 0
    assert parse_dt("") is None and parse_dt("엉터리") is None
    assert merge._dt("2026-11-13").tzinfo == KST
    assert output._dt("2026-11-13").tzinfo == KST


def test_load_canonical_other_report_stops(tmp_path: Path):
    pr = Project(tmp_path)
    pr.ensure()
    pr.canonical.write_text(json.dumps({"project": {"report_type": "blue"}}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        cli._load_canonical(pr, "diag")
    assert "prepare -r diag" in str(e.value)
    assert cli._load_canonical(pr, "blue")["project"]["report_type"] == "blue"
    (pr.work / "diag").mkdir(parents=True)
    (pr.work / "diag" / "canonical.json").write_text(json.dumps({"project": {"report_type": "diag"}}),
                                                     encoding="utf-8")
    assert cli._load_canonical(pr, "diag")["project"]["report_type"] == "diag"
