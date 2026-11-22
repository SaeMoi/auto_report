"""2026-11-16 블루팀 피드백: 노션 원문 깨짐 정리, 룰 범위, 표 칸 파이프, 출력 전 검사."""
from reportgen.intake.mapping import rule_nums
from reportgen.intake.pages import clean_text, parse_markdown, first_table
from reportgen.render.docx import _split_row
from reportgen.render.markdown import _cell, _hosts
from reportgen.validate import output


def test_clean_text():
    assert clean_text("| [rule.id](http://rule.id) | level |") == "| rule.id | level |"
    assert clean_text("[soc-reload.sh](http://soc-reload.sh)로 확인") == "soc-reload.sh로 확인"
    assert clean_text("[문서](https://example.com/a)") == "[문서](https://example.com/a)"   # 진짜 링크는 둠
    assert clean_text("/srv/api/logs/http://localhost_access_log.%Y.txt") == "/srv/api/logs/localhost_access_log.%Y.txt"
    assert clean_text("페이로드 **proto**[shell]=/bin/sh") == "페이로드 __proto__[shell]=/bin/sh"
    assert clean_text("**중요**") == "**중요**"
    _, _, blocks = parse_markdown("# t\n\n## 경보\n\n| [rule.id](http://rule.id) | level |\n| --- | --- |\n| 100123 | 9 |\n")
    assert first_table(blocks)[0]["rule.id"] == "100123"


def test_rule_nums():
    assert rule_nums("100101~100126") == list(range(100101, 100127))
    assert rule_nums("100101, 100106") == [100101, 100106]
    assert rule_nums("31101, 100105-100107") == [31101, 100105, 100106, 100107]


def test_cell_pipe_roundtrip():
    c = _cell("(?i)(?:__proto__|constructor)")
    assert c == "(?i)(?:__proto__\\|constructor)"
    assert _split_row(f"| F-02 | {c} |") == ["F-02", "(?i)(?:__proto__|constructor)"]


def test_hosts():
    hs = ["http://sesacedu.store (sesacedu-dmz-web-01)", "http://admin.sesacedu.store (sesacedu-mgmt-admindb-01)",
          "sesacedu-mgmt-admindb-01", "sesacedu-mgmt-admindb-01 (Docker)"]
    assert _hosts(hs) == "http://sesacedu.store (sesacedu-dmz-web-01), http://admin.sesacedu.store (sesacedu-mgmt-admindb-01)"


def test_output_checks():
    data = {"project": {"authors": [{"name": "a"}], "revisions": [{}], "period": {"start": "2026-11-01"}},
            "blue": {
                "response_procedure": {"min_level": 7},
                "verification_conditions": {"ntp_checked": False},
                "test_cases": [
                    {"test_id": "D-07", "status": "executed", "executed_at": "2026-11-15T16:51:53+09:00",
                     "outcome": "detected", "score": 4, "gap": None, "latency_sec": 0,
                     "alerts": [{"rule_id": 100126, "level": 6}]},
                    {"test_id": "D-08", "status": "executed", "executed_at": "2026-11-15T16:51:53+09:00",
                     "outcome": "not_detected", "score": 1, "gap": "visibility", "alerts": []},
                ],
                "detection_fixes": [{"fix_id": "F-08", "test_ids": ["D-08"], "rule_ids": [100122],
                                     "categorization": {"gap": "process"}, "priority": {"level": 9},
                                     "rule_source": "", "retest": {"at": "2026-11-15T16:51:53+09:00", "score_after": 4}}],
            }}
    rules = {i["rule"] for i in output.run("blue", data, "본문 [AI 작업 대기]")}
    assert {"O-01", "O-02", "O-04", "O-06", "O-07", "O-08", "O-11"} <= rules


def test_chart_xml_and_docx(tmp_path):
    from docx import Document
    from reportgen.render import chart
    from reportgen.render.markdown import metric_charts
    m = {"before": {"detection_rate": 30.8, "avg_score": 1.6, "blocked": 0, "detected": 8, "not_detected": 18,
                    "score_dist": [0, 18, 0, 8, 0, 0]},
         "after": {"detection_rate": 69.2, "avg_score": 3.0, "blocked": 2, "detected": 16, "not_detected": 8,
                   "score_dist": [0, 8, 0, 5, 11, 2]}}
    c = metric_charts(m)
    doc = Document()
    chart.add(doc, c["row"])
    chart.add(doc, c["dist"])
    out = tmp_path / "c.docx"
    doc.save(out)
    import zipfile
    names = zipfile.ZipFile(out).namelist()
    assert sum(n.startswith("word/charts/chart") for n in names) == 4
    xml = zipfile.ZipFile(out).read("word/charts/chart1.xml").decode()
    assert "69.2" in xml and "&quot;%&quot;" in xml


def test_asset_agent_mismatch():
    from reportgen.build.assets import asset_map, mismatches
    data = {"assets": [{"asset_id": "A-01", "name": "사용자 웹", "host": "http://x.store (web-01)", "zone": "external_dmz"},
                       {"asset_id": "A-02", "name": "관리자", "host": "admin-01 (Docker)", "zone": "internal_admin"}],
            "blue": {"log_sources": [{"source": "웹", "asset_id": "A-01", "agent": "001 (web-01)"},
                                     {"source": "관리자 접근", "asset_id": "A-02", "agent": "001 (web-01)"},
                                     {"source": "관리자 감사", "asset_id": "A-02", "agent": "002 (admin-01)"}]}}
    am = asset_map(data)
    assert am["A-01"]["agent_no"] == "001" and am["A-02"]["agent_no"] == "002" and am["A-02"]["server"] == "admin-01"
    mm = mismatches(data)
    assert len(mm) == 1 and mm[0]["suggest"] == "A-01"
