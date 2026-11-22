"""2026-11-16 피드백: 그림·설명 교차 서술, 증거 번호 물결 표기, 그림 설명 형식 통일."""
from reportgen import cli
from reportgen.intake.mapping import build_flow, clean_caption
from reportgen.intake.pages import Block
from reportgen.render.markdown import _idrange

from test_lenient import make


def test_idrange():
    ids = [f"E-{n:03d}" for n in (67, 68, 69, 70, 71, 72, 75, 77, 78)]
    assert _idrange(ids) == "E-067~072, E-075, E-077, E-078"
    assert _idrange([]) == "-"
    assert _idrange(["E-001", "E-500", "E-501", "E-502"]) == "E-001, E-500~502"


def test_clean_caption():
    for name in ("image.png", "Screenshot 2026-11-07 at 11.51.18 PM.png", "스크린샷 2026-11-13 오전 10.19.48.png",
                 "image 3.png", ""):
        assert clean_caption(name) == "", name
    assert clean_caption("[정상 다운로드 요청]") == "정상 다운로드 요청"


def test_build_flow_order():
    blocks = [Block("paragraph", "**Write-up**"), Block("paragraph", "첫 설명"), Block("image", "a.png", path="a"),
              Block("paragraph", "둘째 설명"), Block("bullet", "목록 1"), Block("bullet", "목록 2"),
              Block("image", "b.png", path="b"), Block("code", "GET / HTTP/1.1")]
    flow = build_flow(blocks, {2: "r#0", 6: "r#1"})
    assert flow == [{"text": "첫 설명"}, {"ref": "r#0"}, {"text": "둘째 설명\n- 목록 1\n- 목록 2"}, {"ref": "r#1"},
                    {"code": "GET / HTTP/1.1", "lang": ""}]


def test_interleaved_report(tmp_path):
    pr = make(tmp_path)
    cli.main(["prepare", str(pr), "-r", "diag"])
    import json
    data = json.loads((pr / "build" / "canonical.json").read_text(encoding="utf-8"))
    ev = data["evidence"][0]
    # 파일 이름(image.png)도, 그림 뒤 설명 문단도 캡션으로 쓰지 않음 → 기본 형식
    assert ev["caption"] == "V-01-1 화면" and ev["caption_src"] == "auto"
    i1 = data["instances"][0]
    assert [list(s)[0] for s in i1["flow"]] == ["evidence_id", "text", "code"]
    tasks = [json.loads(x) for x in (pr / "work" / "diag" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    cap = next(t for t in tasks if t["field"] == "evidence.caption")
    assert cap["image"].endswith(".png") and "싱글쿼테이션" in cap["context"]["text_after_image"]
    assert any(t["field"] == "finding_instance.flow" for t in tasks)
    cli.main(["ai", str(pr), "-r", "diag", "-a", "fake"])
    cli.main(["render", str(pr), "-r", "diag", "--draft"])
    md = next((pr / "output").glob("diag_*draft.md")).read_text(encoding="utf-8")
    sec = md[md.index("상세내용 — V-01-1"):]
    assert sec.index("[그림 E-001]") < sec.index("싱글쿼테이션") < sec.index("```text\nPOST /api/admin/login")
    assert "[그림 E-001] 재현 결과 화면" in md
