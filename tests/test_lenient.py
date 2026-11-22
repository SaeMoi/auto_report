"""완화 기준: 팀 기존 양식(소제목 없는 상세설명, 빈 R2 본문)으로도 진단 보고서 초안이 나오는지(노션 P1은 옛 「결과 보고서」 행만 있음 → 대체 규칙)."""
from pathlib import Path

from reportgen import cli

H = "0123456789abcdef0123456789abcdef"

PAGE1 = """# 관리자 로그인 인증 우회 (SQL 인젝션)

건 ID: V-01-1

## **1. 취약점 개요**

| **항목** | **내용** |
| --- | --- |
| 취약점명 | 관리자 로그인 인증 우회 |
| 점검대상 | 관리자 웹 |
| 발견 경로 | 이메일 입력칸에 싱글쿼터 입력 |
| 취약점 설명 | 이메일 입력값이 로그인 쿼리에 문자열로 그대로 결합된다 |
| 영향도(CVSS 3.1) | Critical (9.8) — 근거 |
| CVSS Vector | **`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`** |

## **2. 취약점 상세설명**

- Write-up
    
    ![image.png](shot/image.png)
    
    싱글쿼테이션을 닫아주니 서버 오류가 아닌 비번이 틀렸다고 나온다.
    
    ```
    POST /api/admin/login
    Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwiYXV0aCI6M30.abcDEF123456xyz
    {"email":"admin@example.test","password":"Secret!234"}
    ```
    

---

## **3. 악용 시나리오**

- 비밀번호 없이 로그인된다.
- 관리자 JWT가 발급된다.

---

## **4. 조치방안**

1. 값은 ? 바인딩으로 분리한다.
2. DB 예외를 일반 오류 메시지로 돌려준다.
"""

PAGE2 = """# 로그인 페이지

### 1. 취약점 개요

| 항목 | 내용 |
| --- | --- |
| 영향도(CVSS 3.1) | High (7.5) |
| CVSS Vector | CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N |

### 2. 취약점 상세설명

로그인 화면에서도 같은 방식으로 오류가 난다.
"""


def _csv(path: Path, head: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("﻿" + head + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def make(root: Path) -> Path:
    pr = root / "t1"
    plan, red = pr / "input/plan", pr / "input/notion/red"
    _csv(plan / f"문서 정보 {H}.csv", "문서명,문서 종류,버전,수행 시작일,수행 종료일,검토자,보안 등급,프로젝트",
         ["결과 보고서,결과 보고서,,,,,대외비 (팀 내부용),시험 프로젝트"])
    _csv(plan / f"자산 {H}.csv", "자산명,자산 ID,호스트,구역,역할,기술 스택,접근 통제,중요도,범위",
         ["사용자 웹,A-01,example.test,외부(DMZ),웹,Spring,공개,,범위 내",
          "관리자 API,A-03,admin,관리·내부,API,Node,지정 IP,,범위 내"])
    _csv(plan / f"목표 {H}.csv", "목표,목표 ID,구분,달성 판단 기준,결과,시나리오", [])
    _csv(red / f"취약점 건 {H}.csv", "취약점명,건 ID,취약점 ID,자산,접근경로,위험도,마스킹 완료,조치 상태",
         ["관리자 로그인 인증 우회 (SQL 인젝션),V-01-1,V-01,A-03,POST /api/admin/login,High,No,",
          "로그인 페이지,V-01-2,V-01,,,High,No,"])
    d = red / "취약점 건"
    d.mkdir(parents=True)
    (d / f"관리자 로그인 인증 우회 (SQL 인젝션) {H}.md").write_text(PAGE1, encoding="utf-8")
    (d / f"로그인 페이지 {H}.md").write_text(PAGE2, encoding="utf-8")
    (d / "shot").mkdir()
    from PIL import Image
    Image.new("RGB", (40, 20), "white").save(d / "shot" / "image.png")
    _csv(red / f"취약점 {H}.csv", "취약점명,취약점 ID,취약점 유형,CWE,분류 확정,조치 구분,코드 검토 완료",
         ["SQL Injection,V-01,A05 Injection,CWE-89,확정,,No"])
    (red / "취약점").mkdir()
    (red / "취약점" / f"SQL Injection {H}.md").write_text("# SQL Injection\n\n## 개요\n\n## 악용 시나리오\n\n## 조치방안\n", encoding="utf-8")
    _csv(red / f"진단 항목 판정 {H}.csv", "항목명,항목 코드,판정: A-01,판정: A-03,점검 취약점,비고",
         ["Injection,A05,,,,", "Broken Access Control,A01,,,,"])
    return pr


def test_lenient_draft(tmp_path):
    pr = make(tmp_path)
    cli.main(["prepare", str(pr), "-r", "diag"])
    import json
    data = json.loads((pr / "build" / "canonical.json").read_text(encoding="utf-8"))
    issues = json.loads((pr / "work" / "diag" / "intake_issues.json").read_text(encoding="utf-8"))
    errs = [i for i in issues if i["level"] == "error"]
    assert not errs, errs
    f = data["findings"][0]
    assert "문자열로 그대로 결합" in f["overview"] and f["remediation"]["steps"]
    i1, i2 = data["instances"]
    assert i1["cvss"]["score"] == 9.8 and i1["poc"]["freeform"] and "싱글쿼테이션" in i1["poc"]["explanation"]
    assert i2["freeform"] and i2["status"] == "open"
    # 자동 마스킹: 체크가 꺼져 있어도 가린 값으로 AI 작업이 만들어지고, 원래 값은 어디에도 남지 않음
    canon = (pr / "build" / "canonical.json").read_text(encoding="utf-8")
    tasks = (pr / "work" / "diag" / "tasks.jsonl").read_text(encoding="utf-8")
    for secret in ("eyJhbGciOiJIUzI1NiJ9", "Secret!234", "admin@example.test"):
        assert secret not in canon and secret not in tasks
    assert "[JWT 가림]" in canon and tasks.strip()
    assert any(i["rule"] == "자동 마스킹" for i in issues)
    cli.main(["ai", str(pr), "-r", "diag", "-a", "fake"])
    cli.main(["render", str(pr), "-r", "diag", "--draft"])
    md = next((pr / "output").glob("diag_*draft.md")).read_text(encoding="utf-8")
    assert "SQL Injection" in md and "상세 설명" in md
