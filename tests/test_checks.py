"""AI 결과 검사(R-14·R-15·R-17·R-27)와 문서 변환 단위 시험."""
from __future__ import annotations

from reportgen.ai.check import check_result
from reportgen.render import docx as docx_render


def _task(**kw):
    t = {"task_id": "V-01:finding.overview", "mode": "polish", "field": "finding.overview", "target_id": "V-01",
         "source_text": "GET /search 의 keyword 파라미터에서 152건이 조회됨", "context": {}, "allowed_ids": ["V-01"],
         "length": {}}
    t.update(kw)
    return t


def test_polish_keeps_numbers_and_paths():
    issues = check_result(_task(), {"text": "검색 기능에서 회원 정보가 조회됨"})
    rules = {(i["rule"], i["msg"].split(":")[0]) for i in issues}
    assert any(r == "R-27" for r, _ in rules)


def test_unknown_id_flagged():
    issues = check_result(_task(mode="write", source_text=None), {"text": "V-09에서 확인됨"})
    assert any(i["rule"] == "R-15" and "V-09" in i["msg"] for i in issues)


def test_clean_polish_has_no_r27():
    src = "GET /search 의 keyword 파라미터에서 152건이 조회됨"
    issues = check_result(_task(source_text=src), {"text": src})
    assert not [i for i in issues if i["rule"] == "R-27"]


def test_docx_converter(tmp_path):
    md = "# 제목\n\n## 1. 장\n\n문단 **굵게** `코드`\n\n- 항목\n  1. 하위\n\n| 가 | 나 |\n| --- | --- |\n| 1 | 2 |\n\n```text\nGET / HTTP/1.1\n```\n"
    out = docx_render.convert(md, tmp_path / "t.docx", base_dir=tmp_path)
    from docx import Document
    d = Document(str(out))
    assert len(d.tables) == 2 and d.tables[0].cell(1, 1).text == "2"   # 두 번째는 코드 블록 상자
    assert d.tables[1].cell(0, 0).text == "GET / HTTP/1.1"
    assert any("굵게" in p.text for p in d.paragraphs)


def test_sentence_count_with_id_parens():
    from reportgen.ai.check import sentences
    assert len(sentences("구문을 넣음(V-01-1). 결과를 내려받음(S1-STEP1). 152건을 확보하였음.")) == 3
