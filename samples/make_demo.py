"""시연용 가짜 노션 내보내기(Markdown & CSV)를 만듦. 실제 대상·계정·IP가 아닌 예시 값만 씀.

  python samples/make_demo.py            → samples/demo/input/... 를 새로 씀
그 뒤:
  reportgen prepare samples/demo -r diag
  reportgen ai samples/demo -r diag -a fake
  reportgen check samples/demo -r diag
  reportgen render samples/demo -r diag --draft
"""
from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "demo"
INPUT = ROOT / "input"


def h(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def png(path: Path, text: str, color=(230, 236, 245)) -> None:
    from PIL import Image, ImageDraw
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (640, 260), color)
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 630, 250], outline=(90, 110, 140), width=3)
    d.text((30, 30), "DEMO SCREENSHOT", fill=(40, 40, 40))
    d.text((30, 70), text, fill=(20, 20, 120))
    img.save(path)


def write_db(folder: Path, name: str, rows: list[tuple[str, dict, str]]) -> None:
    """rows = (제목, 속성, 본문 Markdown). 노션 내보내기와 같은 이름 규칙으로 씀."""
    hid = h(name)
    folder.mkdir(parents=True, exist_ok=True)
    cols = ["이름"]
    for _, props, _ in rows:
        for k in props:
            if k not in cols:
                cols.append(k)
    with (folder / f"{name} {hid}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for title, props, _ in rows:
            w.writerow([title] + [props.get(c, "") for c in cols[1:]])
    d = folder / f"{name} {hid}"
    d.mkdir(exist_ok=True)
    for title, props, body in rows:
        if body is None:
            continue
        (d / f"{title} {h(title)}.md").write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")


def single(folder: Path, name: str, body: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name} {h(name)}.md").write_text(f"# {name}\n\n{body.strip()}\n", encoding="utf-8")


# ── 수행 계획(P1~P3) ──────────────────────────────────────────
P1_BODY = """
## 작성자

| 이름 | 역할 | 담당 영역 | 담당 장 | 연락처 |
| --- | --- | --- | --- | --- |
| 홍길동 | PM, 레드팀 | 웹 진단 | 1, 4, 5 | pm@example.test |
| 이몽룡 | 레드팀 | 시나리오 모의해킹 | 6, 7 | red@example.test |
| 성춘향 | 블루팀 | 관제·탐지 | 블루 전체 | blue@example.test |

## 개정 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
| --- | --- | --- | --- |
| 0.1 | 2026-11-20 | 홍길동 | 초안 |
| 1.0 | 2026-11-27 | 홍길동 | 검토 반영, 발행 |
| 1.1 | 2026-12-04 | 홍길동 | 이행 점검 결과(8장) 추가 |

## 진단 목적

데모 쇼핑몰 서비스의 외부 노출 웹과 관리 영역을 대상으로 OWASP Top 10:2025 기준 취약점을 진단하고, 공격 시나리오로 실제 침해 가능성을 확인함.
진단 결과는 블루팀 탐지 검증의 입력으로 씀.

## 요약 메모

웹 진단과 시나리오 모의해킹을 2주간 수행함. 외부 공격자 기준으로 관리자 권한 획득까지 가능함을 확인함.

## 사용 도구

- Burp Suite Community
- sqlmap
- curl

## 테스트 계정

| 계정 | 권한 |
| --- | --- |
| demo_user1 | 일반 회원 |
| demo_user2 | 일반 회원 |

## 일정

| 단계 | 기간 | 내용 |
| --- | --- | --- |
| 준비 | 2026-11-09 ~ 2026-11-10 | 범위 확정, 계정 발급 |
| 진단 | 2026-11-11 ~ 2026-11-15 | OWASP 범주별 수동 진단 |
| 모의해킹 | 2026-11-16 ~ 2026-11-18 | 시나리오 S1 수행 |
| 보고 | 2026-11-19 ~ 2026-11-20 | 결과 보고서 작성 |

## 수행 조건

| 단계 | 출발지 IP | IP 허용 | Active Response | 시작 조건 |
| --- | --- | --- | --- | --- |
| 진단 | 198.51.100.10 | 허용 | 끔 | 회원 계정 |
| 모의해킹 | 203.0.113.50 | 해제 | 켬 | 외부 공격자 |

## 잘 된 보안 사항 메모

| 항목 | 효과 | 근거 ID |
| --- | --- | --- |
| 관리 콘솔 IP 제한 | 외부에서 관리 콘솔 직접 접근 차단 | S1-STEP3 |
"""

P2 = [
    ("데모 쇼핑몰 웹", {"자산 ID": "A-01", "호스트": "shop.demo.example", "공인 IP": "192.0.2.10",
                    "사설 IP": "10.0.1.10", "구역": "외부(DMZ)", "역할": "웹 서비스", "기술 스택": "Nginx, Spring Boot",
                    "열린 포트": "80, 443", "접근 통제": "전체 공개", "중요도": "상", "와주 에이전트": "001",
                    "시작 조건": "외부 공격자, 회원 계정", "범위": "범위 내"}, ""),
    ("데모 관리 콘솔", {"자산 ID": "A-02", "호스트": "admin.demo.example", "공인 IP": "",
                    "사설 IP": "10.0.2.20", "구역": "관리·내부", "역할": "관리자 기능", "기술 스택": "Django",
                    "열린 포트": "8443", "접근 통제": "사내 IP만 허용", "중요도": "상", "와주 에이전트": "002",
                    "시작 조건": "침해 가정", "범위": "범위 내"}, ""),
    ("데모 API 서버", {"자산 ID": "A-03", "호스트": "api.demo.example", "공인 IP": "192.0.2.11",
                    "사설 IP": "10.0.1.11", "구역": "외부(DMZ)", "역할": "모바일 API", "기술 스택": "Node.js, Express",
                    "열린 포트": "443", "접근 통제": "전체 공개", "중요도": "중", "와주 에이전트": "003",
                    "시작 조건": "회원 계정", "범위": "범위 내"}, ""),
]

P3 = [
    ("회원 개인정보 대량 조회", {"목표 ID": "O-1", "구분": "1차", "달성 판단 기준": "다른 회원 100명 이상 정보 조회",
                         "결과": "달성", "시나리오": "S1"}, ""),
    ("관리자 권한 획득", {"목표 ID": "O-2", "구분": "2차", "달성 판단 기준": "관리 콘솔 로그인",
                    "결과": "부분 달성", "시나리오": "S1"}, ""),
]

# ── 레드팀(R1~R7) ─────────────────────────────────────────────
R2 = [
    ("SQL 인젝션", {"취약점 ID": "V-01", "취약점 유형": "A05 Injection", "CWE": "CWE-89", "분류 확정": "확정",
                 "조치 구분": "즉시", "근본 원인": "입력값 검증 부재", "참고 링크": "https://cwe.mitre.org/data/definitions/89.html",
                 "코드 검토 완료": "Yes"}, """
## 개요

상품 검색과 주문 조회 기능이 사용자 입력을 SQL 문에 그대로 이어 붙여 실행함.
입력값이 쿼리 구조를 바꿀 수 있어 DB의 다른 테이블까지 조회됨.

## 악용 시나리오

확인한 것: 검색어 파라미터로 회원 테이블의 이메일·전화번호를 조회함.
가능성: 같은 방법으로 주문·결제 테이블 조회도 가능할 것으로 판단함.

## 원인

MyBatis 매퍼에서 `${keyword}` 치환을 사용함.

## 조치방안

- 매퍼의 `${}` 치환을 `#{}` 바인딩으로 바꿈
- DB 계정 권한을 조회 대상 테이블로 제한함
- 검색어 길이를 50자로 제한함

## 취약한 코드

```xml
SELECT * FROM product WHERE name LIKE '%${keyword}%'
```

## 수정한 코드

```xml
SELECT * FROM product WHERE name LIKE CONCAT('%', #{keyword}, '%')
```
"""),
    ("다른 사용자 주문 조회(IDOR)", {"취약점 ID": "V-02", "취약점 유형": "A01 Broken Access Control", "CWE": "CWE-639",
                           "분류 확정": "확정", "조치 구분": "즉시", "근본 원인": "서버 측 권한 확인 누락"}, """
## 개요

주문 상세 API가 주문 번호만 확인하고 요청한 회원의 주문인지 확인하지 않음.

## 악용 시나리오

확인한 것: 주문 번호를 1씩 바꿔 다른 회원 주문 120건의 배송지를 조회함.
가능성: 주문 번호가 연속이라 전체 주문 조회가 가능할 것으로 판단함.

## 조치방안

- 주문 조회 시 세션의 회원 번호와 주문의 회원 번호를 비교함
- 주문 번호를 예측하기 어려운 값(UUID)으로 바꿈
"""),
    ("관리 콘솔 기본 계정 사용", {"취약점 ID": "V-03", "취약점 유형": "A07 Authentication Failures", "CWE": "CWE-1392",
                         "분류 확정": "확정", "조치 구분": "단기", "근본 원인": "배포 절차에 초기 계정 변경 단계 없음"}, """
## 개요

관리 콘솔이 설치 시 만든 기본 관리자 계정과 비밀번호를 그대로 사용함.

## 악용 시나리오

확인한 것: 내부망에서 기본 계정으로 관리 콘솔에 로그인함.
가능성: 내부망에 들어온 공격자는 모든 관리 기능을 쓸 수 있음.

## 조치방안

- 기본 계정 비밀번호를 바꾸고 계정 이름을 변경함
- 관리 콘솔에 2단계 인증을 적용함
"""),
    ("서버 버전 정보 노출", {"취약점 ID": "V-04", "취약점 유형": "A02 Security Misconfiguration", "CWE": "CWE-200",
                     "분류 확정": "확정", "조치 구분": "중기", "근본 원인": "기본 설정 사용"}, """
## 개요

응답 헤더 Server와 X-Powered-By에 웹 서버와 프레임워크 버전이 노출됨.

## 조치방안

- Nginx `server_tokens off` 설정
- Express `app.disable('x-powered-by')` 설정
"""),
]


def r1_rep(iid, fid, asset, access, sev, score, vector, steps, request, expl, response, facts, shot, extra=None):
    props = {"건 ID": iid, "취약점 ID": fid, "자산": asset, "접근경로": access, "위험도": sev, "발견 방법": "수동",
             "조치 상태": "미조치", "마스킹 완료": "Yes"}
    props |= extra or {}
    steps_md = "\n".join(f"{n}. {s}" for n, s in enumerate(steps, 1))
    body = f"""
## 1. 취약점 개요

| 항목 | 내용 |
| --- | --- |
| 발견 경로 | 수동 진단 |
| 점검대상 | {asset} |
| 영향도(CVSS 3.1) | {sev.capitalize()} ({score}) |
| CVSS Vector | `{vector}` |

## 2. 취약점 상세설명

### 위치

{access}

### 재현 과정

{steps_md}

### 공격 요청

```http
{request}
```

### 공격 설명

{expl}

### 결과

```http
{response}
```

{facts}

![{shot}]({iid}/{shot}.png)

{shot}
"""
    return (iid, props, body)


def r1_other(iid, fid, asset, access, sev, score, vector, diff, extra=None):
    props = {"건 ID": iid, "취약점 ID": fid, "자산": asset, "접근경로": access, "위험도": sev, "발견 방법": "수동",
             "조치 상태": "미조치", "마스킹 완료": "Yes"} | (extra or {})
    body = f"""
## 1. 취약점 개요

| 항목 | 내용 |
| --- | --- |
| 발견 경로 | 수동 진단 |
| 점검대상 | {asset} |
| 영향도(CVSS 3.1) | {sev.capitalize()} ({score}) |
| CVSS Vector | `{vector}` |

## 2. 취약점 상세설명

### 대표 건과 다른 점

{diff}

```http
GET {access.split()[-1]} HTTP/1.1
Host: api.demo.example
```
"""
    return (iid, props, body)


R1 = [
    r1_rep("V-01-1", "V-01", "A-01", "GET /search?keyword=", "high", 8.6,
           "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N",
           ["상품 검색창에 작은따옴표를 넣어 SQL 오류가 나는지 확인함", "UNION 구문으로 열 개수를 맞춤",
            "회원 테이블의 이메일 열을 조회함"],
           "GET /search?keyword=a%27%20UNION%20SELECT%20email,2,3%20FROM%20member--%20 HTTP/1.1\nHost: shop.demo.example",
           "작은따옴표로 문자열을 닫고 UNION SELECT로 member 테이블의 email 열을 상품 이름 자리에 붙임. 끝의 -- 는 뒤쪽 쿼리를 주석 처리함",
           "HTTP/1.1 200 OK\n\n[{\"name\":\"user1@***.test\"},{\"name\":\"user2@***.test\"}]",
           "회원 이메일 152건이 상품 목록 자리에 나타남", "회원 이메일 조회 결과",
           {"시나리오 단계": "S1-STEP1"}),
    r1_other("V-01-2", "V-01", "A-03", "GET /api/orders?status=", "medium", 6.5,
             "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
             "로그인한 회원만 쓸 수 있는 주문 목록 API의 status 파라미터에서 발생함. 시간 지연 방식으로만 확인됨"),
    r1_rep("V-02-1", "V-02", "A-03", "GET /api/orders/{orderId}", "high", 7.7,
           "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:N",
           ["demo_user1로 로그인해 내 주문 번호를 확인함", "주문 번호를 1씩 바꿔 요청함"],
           "GET /api/orders/100231 HTTP/1.1\nHost: api.demo.example\nAuthorization: Bearer ***",
           "orderId만 바꾸고 토큰은 demo_user1 것을 그대로 씀. 서버는 토큰의 회원과 주문의 회원을 비교하지 않음",
           "HTTP/1.1 200 OK\n\n{\"orderId\":100231,\"receiver\":\"김**\",\"address\":\"서울시 ***\"}",
           "다른 회원 주문 120건의 수령인·주소가 응답됨", "다른 회원 주문 조회 결과",
           {"시나리오 단계": "S1-STEP2"}),
    r1_rep("V-03-1", "V-03", "A-02", "POST /admin/login", "critical", 9.1,
           "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
           ["내부망 PC에서 관리 콘솔 로그인 화면에 접속함", "제품 설명서의 기본 계정으로 로그인함"],
           "POST /admin/login HTTP/1.1\nHost: admin.demo.example\n\nusername=admin&password=********",
           "제품 설명서에 공개된 초기 계정을 그대로 넣음",
           "HTTP/1.1 302 Found\nLocation: /admin/dashboard",
           "관리자 대시보드에 접속됨", "관리 콘솔 로그인 성공", {"시나리오 단계": "S1-STEP4"}),
    r1_rep("V-04-1", "V-04", "A-01", "GET /", "low", 3.7,
           "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N",
           ["메인 페이지 응답 헤더를 확인함"], "GET / HTTP/1.1\nHost: shop.demo.example",
           "일반 요청으로 응답 헤더만 봄", "HTTP/1.1 200 OK\nServer: nginx/1.18.0", "Server 헤더에 버전이 나타남",
           "응답 헤더의 서버 버전"),
    r1_other("V-04-2", "V-04", "A-03", "GET /api/health", "low", 3.7,
             "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N", "X-Powered-By: Express 헤더가 노출됨"),
]

OWASP_ITEMS = [("A01", "Broken Access Control", "양호", "양호", "취약", "IDOR"),
               ("A02", "Security Misconfiguration", "취약", "양호", "취약", ""),
               ("A03", "Software Supply Chain Failures", "양호", "양호", "양호", ""),
               ("A04", "Cryptographic Failures", "양호", "양호", "양호", ""),
               ("A05", "Injection", "취약", "양호", "취약", "SQL Injection, Reflected XSS, Stored XSS"),
               ("A06", "Insecure Design", "양호", "양호", "양호", ""),
               ("A07", "Authentication Failures", "양호", "취약", "양호", ""),
               ("A08", "Software or Data Integrity Failures", "양호", "해당 없음", "양호", ""),
               ("A09", "Security Logging and Alerting Failures", "양호", "양호", "양호", ""),
               ("A10", "Mishandling of Exceptional Conditions", "양호", "양호", "양호", "")]
R3 = [(name, {"항목 코드": code, "판정: A-01": a1, "판정: A-02": a2, "판정: A-03": a3, "점검 취약점": chk}, None)
      for code, name, a1, a2, a3, chk in OWASP_ITEMS]

R4 = [("외부에서 관리자 권한까지", {"시나리오 ID": "S1", "목표": "O-1, O-2", "시작 조건": "외부 공격자",
                            "결과 요약": "회원 정보 조회 성공, 관리 콘솔은 내부망 경유로만 접근", "마스킹 완료": "Yes",
                            "확인 범위": "회원 정보 조회부터 관리자 로그인까지 확인. 관리자 기능으로 데이터 변경은 미시험",
                            "수행일": "2026-11-16 → 2026-11-17", "작성자": "이몽룡"}, """
## 공격 체인 다이어그램

```text
[공격자 203.0.113.50] -> A-01 검색 SQL 인젝션 -> A-03 주문 순회 -> (A-02 외부 차단) -> 내부 PC -> A-02 관리 콘솔
```

## 단서와 경로 선택

검색 결과 페이지가 작은따옴표 하나에 SQL 오류 문구를 그대로 보여 줌. 그래서 검색 파라미터로 시작함.

- 주문 API가 번호만 바꾸면 응답하는 것을 진단 때 확인함(V-02-1)

## 주의점과 실패한 시도

| 구분 | 내용 | 관련 단계 | 원인 / 막은 통제 |
| --- | --- | --- | --- |
| 작동한 방어 | 외부에서 관리 콘솔 접속이 막힘 | S1-STEP3 | 사내 IP만 허용 |
| 막힌 곳 | UNION 열 개수를 맞추는 데 시간이 걸림 | S1-STEP1 | 오류 문구로 열 수를 셈 |

## 성립 원인

- 검색 쿼리를 문자열로 이어 붙임
- 관리 콘솔 기본 계정이 바뀌지 않음

## 정리 내역

| 대상에 남긴 것 | 위치 | 정리 여부 | 정리 일시 · 확인 방법 |
| --- | --- | --- | --- |
| 관리 콘솔 세션 | A-02 | 정리함 | 2026-11-17 로그아웃 후 세션 목록 확인 |

## 위협 카드

| 위협 카드 | 사용 사유 | 승인자 | 사용 시각(초) |
| --- | --- | --- | --- |
| 내부망 발판 제공 | 외부에서 관리 콘솔이 막혀 침해 가정으로 전환 | 홍길동 | 2026-11-17T14:00:00+09:00 |

## 영향 분석

| 항목 | 내용 |
| --- | --- |
| 유출·변조될 수 있는 정보 | 회원 이메일·전화번호, 주문 배송지 |
| 서비스 영향 | 관리자 기능으로 상품·주문 변경 가능 |
| 실제 사고였다면 | 개인정보 유출 신고 대상 |
| 개별 위험도와의 차이 | V-02는 High이지만 V-01과 이어지면 대량 유출로 커짐 |
""")]


def step(sid, name, purpose, start, end, ip, asset, insts, tech, result, gained="", blocked="", actions=(), logs=(),
         idea="", shot=None, tests="", basis="로그", impact="읽기만 함", why="", inline=None):
    props = {"단계 ID": sid, "목적": purpose, "시작 시각(초)": start, "종료 시각(초)": end, "출발지 IP": ip,
             "대상 자산": asset, "사용 취약점": insts, "ATT&CK 기법": tech, "결과": result, "획득한 것": gained,
             "막힌 이유": blocked, "탐지 검증": tests, "마스킹 완료": "Yes", "시각 근거": basis,
             "대상에 남긴 영향": impact}
    body = "## 수행 내용\n\n" + "\n".join(f"- {a}" for a in actions)
    if inline:   # 수행 내용 안의 그림(그림 바로 아래 문단 = 캡션)
        body += f"\n\n![image.png]({sid}/{inline}.png)\n\n{inline} 화면"
    if why:
        body += f"\n\n## 판단 근거\n\n{why}"
    body += "\n\n## 남아야 하는 로그\n\n" + \
        "\n".join(f"- {x}" for x in logs) + f"\n\n## 탐지 기회\n\n{idea}\n\n## 증거\n\n"
    if shot:
        body += f"![{shot}]({sid}/{shot}.png)\n\n{shot}\n"
    return (name, props, body)


R5 = [
    step("S1-STEP1", "검색 기능 SQL 인젝션으로 회원 정보 조회", "회원 이메일 확보", "2026-11-16T10:02:11+09:00",
         "2026-11-16T10:40:03+09:00", "203.0.113.50", "A-01", "V-01-1", "T1190", "확인", gained="회원 이메일 152건",
         why="검색 결과 화면이 SQL 오류 문구를 그대로 보여 줘 UNION 기반 조회가 가장 빠르다고 봄", inline="S1-STEP1 UNION 요청",
         actions=["검색 파라미터에 UNION 구문을 넣어 member 테이블을 조회함", "결과를 페이지 단위로 내려받음"],
         logs=["Nginx access.log의 keyword 파라미터에 UNION 문자열", "WAS SQL 오류 로그"],
         idea="access.log에서 UNION·작은따옴표가 들어간 검색 요청을 찾음", shot="S1-STEP1 회원 이메일 조회", tests="D-01"),
    step("S1-STEP2", "주문 번호 변경으로 배송지 조회", "다른 회원 배송지 확보", "2026-11-16T11:10:00+09:00",
         "2026-11-16T11:35:42+09:00", "203.0.113.50", "A-03", "V-02-1", "T1190", "성공", gained="주문 120건의 배송지", basis="화면",
         actions=["demo_user1 토큰으로 주문 번호를 1씩 바꿔 요청함"],
         logs=["API 접근 로그의 /api/orders/{id} 연속 요청"], idea="같은 토큰으로 짧은 시간에 서로 다른 주문 번호를 요청하는 패턴",
         tests="D-02"),
    step("S1-STEP3", "외부에서 관리 콘솔 접속 시도", "관리 콘솔 접근", "2026-11-16T13:20:00+09:00",
         "2026-11-16T13:25:10+09:00", "203.0.113.50", "A-02", "", "T1133", "실패",
         blocked="관리 콘솔이 사내 IP만 허용함", actions=["외부에서 admin.demo.example:8443에 접속을 시도함"],
         logs=["방화벽 차단 로그"], idea="방화벽 차단 로그의 8443 포트 외부 접속", tests="D-03"),
    step("S1-STEP4", "내부망에서 기본 계정으로 관리 콘솔 로그인", "관리자 권한 획득", "2026-11-17T14:05:00+09:00",
         "2026-11-17T14:12:30+09:00", "10.0.9.99", "A-02", "V-03-1", "T1078.001", "확인", gained="관리자 세션", impact="관리 콘솔에 세션 1개를 만듦",
         actions=["위협 카드 「내부망 발판 제공」으로 내부 PC에서 접속함", "기본 계정으로 로그인함"],
         logs=["관리 콘솔 인증 로그의 admin 로그인 성공"], idea="평소와 다른 PC에서 admin 계정 로그인",
         shot="S1-STEP4 관리자 대시보드", tests="D-04"),
    step("S1-STEP5", "관리자 기능으로 상품 가격 변경", "데이터 변경 가능성 확인", "", "", "", "A-02", "", "T1565.001",
         "미시험", blocked="운영 데이터 변경은 수행 규칙상 하지 않음", actions=["수행하지 않음(수행 규칙)"], basis="",
         impact="-"),
]

R6 = [("검색 쿼리 바인딩 변경", {"대상 건": "V-01-1, V-01-2", "조치 구분": "코드 수정", "적용 범위": "같은 취약점 전체",
                          "적용 일자": "2026-11-25", "적용 담당": "개발팀", "변경 위치": "ProductMapper.xml"},
       "## 변경 내용\n\n```diff\n- LIKE '%${keyword}%'\n+ LIKE CONCAT('%', #{keyword}, '%')\n```\n"),
      ("주문 조회 소유자 확인 추가", {"대상 건": "V-02-1", "조치 구분": "코드 수정", "적용 범위": "해당 건만",
                             "적용 일자": "2026-11-26", "적용 담당": "개발팀", "변경 위치": "OrderController.js"},
       "## 변경 내용\n\n```diff\n+ if (order.memberId !== req.user.id) return res.status(403).end();\n```\n")]

R7 = [("V-01-1", {"확인한 조치": "검색 쿼리 바인딩 변경", "재진단 일자": "2026-12-02", "결과": "조치 완료",
                  "시나리오 재현": "체인 차단됨", "마스킹 완료": "Yes"}, ""),
      ("V-02-1", {"확인한 조치": "주문 조회 소유자 확인 추가", "재진단 일자": "2026-12-02", "결과": "조치 완료",
                  "시나리오 재현": "체인 차단됨", "마스킹 완료": "Yes"}, "")]

# ── 블루팀(B1~B10) ────────────────────────────────────────────
B1 = """
## 와주 구성

| 항목 | 값 |
| --- | --- |
| 와주 버전 | 4.9.0 |
| 구성 | 단일 노드(매니저·인덱서·대시보드) |
| 현재 성숙도 | 수집·기본 탐지 |
| 다음 성숙도 | 커스텀 탐지·자동 대응 |
| 다음 단계 조건 | 미탐 0건, 오탐률 10% 이하 |

## 설계 판단

- 웹 접근 로그를 우선 수집함
- 관리 콘솔 인증 로그에 커스텀 디코더를 둠

## 알림 및 대응 절차

| 항목 | 값 |
| --- | --- |
| 알림 경로 | 메일, 메신저 |
| 알림 기준 레벨 | 10 |
| 담당자 | 성춘향 |
| 확인 주기 | 업무 시간 30분 |

## 대응 단계

1. 경보 확인
2. 정탐 판단
3. 출발지 IP 차단

## 검증 조건

| 항목 | 값 |
| --- | --- |
| 검증 방식 | 블라인드 |
| 테스터 IP 허용 | 아니오 |
| Active Response | 켬 |
| 기본 룰셋 버전 | 4.9.0 |
| 커스텀 룰 | 100100, 100200 |
| NTP 확인 | 예 |
| 적용 시작(초) | 2026-11-16T09:00:00+09:00 |
| 적용 종료(초) | 2026-11-18T18:00:00+09:00 |
"""

B2 = [("Nginx access.log", {"자산": "A-01", "에이전트": "001", "경로": "/var/log/nginx/access.log", "수집": "Yes",
                            "디코더": "기본", "관련 룰": "31101, 31103", "기준선 시각(초)": "2026-11-15T18:00:00+09:00"}, None),
      ("API 접근 로그", {"자산": "A-03", "에이전트": "003", "경로": "/var/log/api/access.log", "수집": "No",
                     "디코더": "없음", "관련 룰": "", "기준선 시각(초)": "2026-11-15T18:00:00+09:00"}, None),
      ("관리 콘솔 인증 로그", {"자산": "A-02", "에이전트": "002", "경로": "/var/log/admin/auth.log", "수집": "Yes",
                         "디코더": "커스텀", "관련 룰": "100200", "기준선 시각(초)": "2026-11-15T18:00:00+09:00"}, None)]

B3 = [("Active Response", {"모듈": "Active Response", "대상 자산": "A-01", "설정 요약": "웹 공격 룰 발생 시 출발지 차단",
                           "AR 트리거 룰": "31103", "AR 동작": "firewall-drop", "AR 유지 시간(초)": "600"}, None)]


def tc(tid, proc, src, ref, tech, obs, at, ip, outcome, score, gap, alerts="", fix="", ack="", res=""):
    props = {"테스트 ID": tid, "출처": src, "출처 ID": ref, "전술": "Initial Access", "ATT&CK 기법": tech,
             "기대 관측치": obs, "상태": "실행 완료", "실행 시각(초)": at, "출발지 IP": ip, "결과 분류": outcome,
             "점수": str(score), "공백": gap, "개선 조치": fix, "마스킹 완료": "Yes", "확인 시각(초)": ack,
             "판단": "정탐" if ack else "", "조치 완료 시각(초)": res, "대응 담당": "성춘향" if ack else ""}
    body = "## 경보\n\n| rule.id | level | 에이전트 | 경보 시각(초) |\n| --- | --- | --- | --- |\n" + alerts
    if alerts:   # 경보 화면(사진) 예시
        body += f"\n## 증거\n\n![image.png]({tid}/image.png)\n\n대시보드에서 확인한 {tid} 경보\n"
    return (proc, props, body)


B4 = [
    tc("D-01", "검색 파라미터 SQL 인젝션 재현", "시나리오 단계", "S1-STEP1", "T1190", "access.log의 UNION 요청 경보",
       "2026-11-16T10:02:11+09:00", "203.0.113.50", "탐지", 4, "없음",
       "| 31103 | 10 | 001 | 2026-11-16T10:02:20+09:00 |\n", ack="2026-11-16T10:20:00+09:00",
       res="2026-11-16T10:45:00+09:00"),
    tc("D-02", "주문 번호 순회 재현", "시나리오 단계", "S1-STEP2", "T1190", "API 로그의 연속 주문 조회 경보",
       "2026-11-16T11:10:00+09:00", "203.0.113.50", "미탐", 0, "가시성", fix="F-01"),
    tc("D-03", "외부 관리 콘솔 접속 재현", "시나리오 단계", "S1-STEP3", "T1133", "방화벽 차단",
       "2026-11-16T13:20:00+09:00", "203.0.113.50", "차단", 5, "없음",
       "| 31103 | 10 | 001 | 2026-11-16T13:20:04+09:00 |\n", ack="2026-11-16T13:25:00+09:00",
       res="2026-11-16T13:20:05+09:00"),
    tc("D-04", "기본 계정 로그인 재현", "취약점 건", "V-03-1", "T1078.001", "관리 콘솔 admin 로그인 경보",
       "2026-11-17T14:05:00+09:00", "10.0.9.99", "탐지", 2, "탐지 로직",
       "| 100200 | 5 | 002 | 2026-11-17T14:05:30+09:00 |\n", fix="F-02"),
]

B5 = [("API 주문 순회 탐지", {"조치 ID": "F-01", "관련 테스트": "D-02", "목표": "같은 토큰의 주문 번호 순회 탐지",
                          "ATT&CK 기법": "T1190", "공백": "가시성", "룰 level": "10", "level 근거": "개인정보 대량 조회",
                          "rule.id": "100300", "파일": "local_rules.xml", "재검증 시각(초)": "2026-11-24T10:00:00+09:00",
                          "재검증 확인 시각(초)": "2026-11-24T10:05:00+09:00",
                          "재검증 점수": "4", "재검증 결과": "탐지", "마스킹 완료": "Yes"}, """
## 원본 로그 예시

```text
10.0.1.11 - - [16/Nov/2026:11:10:01 +0900] "GET /api/orders/100231 HTTP/1.1" 200 312 user=demo_user1
```

## 룰 전문

```xml
<rule id="100300" level="10" frequency="20" timeframe="60">
  <if_matched_sid>100299</if_matched_sid>
  <same_field>user</same_field>
  <description>같은 사용자의 주문 번호 순회</description>
</rule>
```

## 사각지대·가정

- 여러 계정을 번갈아 쓰면 탐지하지 못함

## 오탐

- 고객센터 직원의 정상 조회
"""),
      ("관리 콘솔 기본 계정 로그인 탐지 강화", {"조치 ID": "F-02", "관련 테스트": "D-04", "목표": "admin 계정 로그인을 높은 레벨로 알림",
                                   "ATT&CK 기법": "T1078.001", "공백": "탐지 로직", "룰 level": "12", "level 근거": "관리자 권한",
                                   "rule.id": "100201", "파일": "local_rules.xml", "재검증 시각(초)": "2026-11-24T11:00:00+09:00",
                                   "재검증 확인 시각(초)": "2026-11-24T11:03:00+09:00",
                                   "재검증 점수": "4", "재검증 결과": "탐지", "마스킹 완료": "Yes"}, """
## 룰 전문

```xml
<rule id="100200" level="5">
  <decoded_as>admin-auth</decoded_as>
  <description>관리 콘솔 로그인</description>
</rule>
<rule id="100201" level="12">
  <if_sid>100200</if_sid>
  <user>admin</user>
  <description>관리 콘솔 admin 로그인</description>
</rule>
```
""")]

B6 = """
## 개요

| 항목 | 값 |
| --- | --- |
| 시나리오 | S1 |
| 최초 인지 시각(초) | 2026-11-16T10:20:00+09:00 |
| 판단 근거 | 31103 경보 |
| 영향 자산 | A-01, A-02 |
| 영향 데이터 | 회원 이메일 |

## 타임라인

| 시각(초) | 출처 | 공격자 행위 | 방어 측 활동 |
| --- | --- | --- | --- |
| 2026-11-16T10:02:11+09:00 | 레드팀 6-2 | SQL 인젝션 | - |
| 2026-11-16T10:20:00+09:00 | 와주 | - | 경보 확인 |

## 봉쇄·제거·복구

- 출발지 IP 차단

## IOC

| 종류 | 값 |
| --- | --- |
| IP | 203.0.113.50 |

## 사후 활동

- API 로그 수집 추가
"""

B7 = [("CIS Ubuntu 22.04", {"자산": "A-01", "조치 전 점수": "48", "조치 후 점수": "71", "주요 미통과 항목": "SSH root 로그인, 패스워드 정책",
                            "취약 패키지(전)": "12", "취약 패키지(후)": "3", "조회 시각(초)": "2026-11-20T10:00:00+09:00"}, None)]
B8 = [("보안그룹 변경", {"이벤트 예시": "AuthorizeSecurityGroupIngress", "수집": "Yes", "탐지 룰": "80202", "비고": ""}, None)]
B9 = [("API 로그 디코더 작성", {"관련 공백": "가시성", "관련 테스트": "D-02", "관련 조치": "F-01", "담당": "성춘향",
                           "기한": "2026-12-10", "상태": "진행"}, None)]
B10 = """
## 집계 기간

| 시작일 | 종료일 | 전체 경보 | 오탐 |
| --- | --- | --- | --- |
| 2026-11-09 | 2026-11-22 | 1840 | 210 |

## 기간별 경보

| 기간 | 경보 건수 |
| --- | --- |
| 1주차 | 820 |
| 2주차 | 1020 |

## 많이 발생한 룰

| rule.id | 건수 |
| --- | --- |
| 31101 | 640 |
| 5710 | 310 |
"""


PLAN_EXTRA = """
## 수행 개요

| 항목 | 내용 |
| --- | --- |
| 수행 유형 | 취약점 진단 + 시나리오 모의해킹 + 블루팀 탐지 검증 |
| 진단 기준 | OWASP Top 10:2025, CWE, CVSS 3.1 |
| 승인자 | 김검토 |

## 네트워크 구성

![인프라 구성도](infra/인프라 구성도.png)

데모 쇼핑몰 인프라 구성도

## 범위

| 구분 | 대상 | 비고 |
| --- | --- | --- |
| 포함 | A-01 ~ A-03 |  |
| 제외 | 서비스 거부(DoS) 공격, 결제 대행사 |  |

## 수행 규칙

- 허용 기법: 웹 공격, 계정 대입 시도(10회 제한), 권한 상승
- 금지 기법: DoS, 실사용자 계정 사용

## 디컨플릭션

- 블루팀은 경보를 확인하면 홍길동에게 레드팀 활동인지 문의함

## 비상 연락

| 역할 | 이름 | 연락 방법 |
| --- | --- | --- |
| 총괄 | 홍길동 | pm@example.test |
"""


def main() -> None:
    for sub in ("input", "evidence", "build", "work", "output"):
        shutil.rmtree(ROOT / sub, ignore_errors=True)
    plan, red, blue = INPUT / "plan", INPUT / "notion" / "red", INPUT / "notion" / "blue"
    write_db(plan, "문서 정보", [("데모 쇼핑몰 보안 점검 결과 보고서",
                               {"프로젝트": "데모 쇼핑몰 보안 점검", "문서 종류": "결과 보고서", "버전": "1.1",
                                "수행 시작일": "2026-11-09", "수행 종료일": "2026-11-20", "보안 등급": "대외비 (팀 내부용)",
                                "검토자": "김검토", "진단 기간": "2026-11-11 ~ 2026-11-15",
                                "모의해킹 기간": "2026-11-16 ~ 2026-11-18"}, P1_BODY),
                              ("데모 쇼핑몰 블루팀 보고서",
                               {"프로젝트": "데모 쇼핑몰 보안 점검", "문서 종류": "블루팀 보고서", "버전": "1.0",
                                "수행 시작일": "2026-11-09", "수행 종료일": "2026-11-24", "보안 등급": "대외비 (팀 내부용)",
                                "검토자": "김검토"}, P1_BODY.replace("| 1.1 | 2026-12-04 | 홍길동 | 이행 점검 결과(8장) 추가 |\n", "")),
                              ("데모 쇼핑몰 수행 계획서",
                               {"프로젝트": "데모 쇼핑몰 보안 점검", "문서 종류": "수행 계획서", "버전": "1.0",
                                "수행 시작일": "2026-11-09", "수행 종료일": "2026-11-24", "보안 등급": "대외비 (팀 내부용)",
                                "검토자": "김검토"}, P1_BODY + PLAN_EXTRA)])
    write_db(plan, "자산", P2)
    write_db(plan, "목표", P3)
    write_db(red, "취약점", R2)
    write_db(red, "취약점 건", R1)
    write_db(red, "진단 항목 판정", R3)
    write_db(red, "시나리오", R4)
    write_db(red, "시나리오 단계", R5)
    write_db(red, "취약점 패치", R6)
    write_db(red, "재진단", R7)
    write_db(blue, "로그 소스", B2)
    write_db(blue, "와주 모듈", B3)
    write_db(blue, "탐지 검증 테스트 케이스", B4)
    write_db(blue, "탐지 전략서", B5)
    write_db(blue, "SCA 결과", B7)
    write_db(blue, "클라우드 감시", B8)
    write_db(blue, "개선 과제", B9)
    single(blue, "관제 환경", B1)
    single(blue, "침해사고 분석", B6)
    single(blue, "운영 통계", B10)
    png(plan / f"문서 정보 {h('문서 정보')}" / "infra" / "인프라 구성도.png", "INFRA DIAGRAM (demo)")
    # 스크린샷(가짜)
    for folder, rows in ((red / f"취약점 건 {h('취약점 건')}", R1), (red / f"시나리오 단계 {h('시나리오 단계')}", R5),
                         (blue / f"탐지 검증 테스트 케이스 {h('탐지 검증 테스트 케이스')}", B4)):
        for title, props, body in rows:
            for line in (body or "").splitlines():
                if line.startswith("!["):
                    rel = line[line.index("(") + 1:line.index(")")]
                    png(folder / rel, rel.split("/")[-1].replace(".png", ""))
    print(f"시연 입력을 만듦: {INPUT}")


if __name__ == "__main__":
    main()
