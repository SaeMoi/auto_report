"""「공격 요청」에 요청 원문 대신 패킷 화면만 둔 대표 건: 그 그림이 요청 자리에 나오고 R-24 경고가 없는지(2026-11-21)."""
import json

from reportgen import cli

from test_lenient import H, make

PAGE = """# 관리자 로그인 인증 우회 (SQL 인젝션)

건 ID: V-01-1

## 1. 취약점 개요

| 항목 | 내용 |
| --- | --- |
| 영향도(CVSS 3.1) | Critical (9.8) |
| CVSS Vector | CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H |

## 2. 취약점 상세설명

**위치**

POST /api/admin/login 이메일 입력칸

**재현 과정**

1. 이메일 칸에 따옴표 입력

![image.png](shot/before.png)

**공격 요청**

![image.png](shot/image.png)

*실제 요청 패킷 화면*

**공격 설명**

이메일 값이 쿼리에 그대로 결합됨

**결과**

![image.png](shot/after.png)

관리자로 로그인됨

## 3. 악용 시나리오

- 비밀번호 없이 로그인

## 4. 조치방안

1. 값 바인딩
"""


def test_request_figs(tmp_path):
    pr = make(tmp_path)
    d = pr / "input/notion/red/취약점 건"
    (d / f"관리자 로그인 인증 우회 (SQL 인젝션) {H}.md").write_text(PAGE, encoding="utf-8")
    from PIL import Image
    Image.new("RGB", (40, 20), "black").save(d / "shot" / "before.png")
    Image.new("RGB", (40, 20), "gray").save(d / "shot" / "after.png")
    cli.main(["prepare", str(pr), "-r", "diag"])
    data = json.loads((pr / "build" / "canonical.json").read_text(encoding="utf-8"))
    i1 = next(i for i in data["instances"] if i["instance_id"] == "V-01-1")
    figs = i1["poc"].get("request_figs")
    assert figs and len(figs) == 1 and not i1["poc"]["request"]
    issues = json.loads((pr / "work" / "diag" / "intake_issues.json").read_text(encoding="utf-8"))
    assert not [i for i in issues if i["rule"] == "R-24" and i["where"] == "V-01-1" and "공격 요청" in i["msg"]]
    cli.main(["ai", str(pr), "-r", "diag", "-a", "fake"])
    cli.main(["render", str(pr), "-r", "diag", "--draft"])
    md = next((pr / "output").glob("diag_*draft.md")).read_text(encoding="utf-8")
    req = md.split("- 공격 요청:")[1].split("- 공격 설명:")[0]
    assert figs[0] in req and "```http" not in req
    assert "잘 된 보안 사항" not in md
    body = md.split("상세내용 — V-01-1")[1].split("상세내용 — V-01-2")[0]
    assert body.count(f"[그림 {figs[0]}]") == 1   # 요청 그림이 뒤 그림 묶음에 또 나오지 않음
