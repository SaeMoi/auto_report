"""자동 마스킹: 노션에서 읽은 글·코드·표에서 비밀 값을 규칙으로 가림(2026-11-16 결정).

- AI로 보내기 전, 보고서에 싣기 전에 이 컴퓨터 안에서 처리함. 모델을 쓰지 않음
- 가린 뒤에는 그 페이지를 「마스킹 완료」로 봄(사람이 체크하지 않아도 됨)
- 스크린샷 속 글자는 가리지 못함. 그림은 사람이 확인해야 함
- 자산 IP·출발지 IP는 보고서에 써야 하는 값이라 가리지 않음
"""
from __future__ import annotations

import re
from collections import Counter

from .pages import Page

SECRET_KEYS = (r"password|passwd|pwd|passwordconfirm|new_?password|old_?password|secret|client_secret|"
               r"api[_-]?key|access[_-]?key|secret[_-]?key|private[_-]?key|aws_secret_access_key")
SESSION_KEYS = r"JSESSIONID|PHPSESSID|SESSION|connect\.sid|sid|session_?id|access_?token|refresh_?token|id_?token"


def _email(m: re.Match) -> str:
    local, domain = m.group(1), m.group(2)
    return f"{local[:2]}***@{domain}"


# (이름, 정규식, 바꿀 값). 위에서부터 차례로 적용함
RULES: list[tuple[str, re.Pattern, object]] = [
    ("개인 키", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[개인 키 가림]"),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"), "[JWT 가림]"),
    ("Authorization 헤더", re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)(?!\*|\[)[A-Za-z0-9._~+/=-]{8,}"),
     r"\1****"),
    ("세션·토큰 값", re.compile(rf"(?i)\b({SESSION_KEYS})(\"?\s*[=:]\s*\"?)(?!\*|\[)[A-Za-z0-9._~+/%-]{{12,}}"),
     r"\1\2****"),
    ("비밀번호·키", re.compile(rf"(?i)\b({SECRET_KEYS})([\"']?\s*[=:]\s*[\"']?)(?!\*|\[)[^\s\"'&*,;<>{{}}]{{3,}}"),
     r"\1\2****"),
    ("AWS 액세스 키", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[AWS 키 가림]"),
    ("AWS 리소스 ID", re.compile(r"\b(i|ami|sg|vpc|subnet|eni|vol|snap|igw|rtb|eipalloc)-[0-9a-f]{8,17}\b"),
     r"\1-****"),
    ("AWS 계정 ARN", re.compile(r"\barn:aws:[a-z0-9-]*:[a-z0-9-]*:\d{12}:\S+"), "[ARN 가림]"),
    ("해시 값", re.compile(r"(?<![0-9A-Fa-f])(?:[0-9a-f]{64}|[0-9a-f]{40}|[0-9a-f]{32})(?![0-9A-Fa-f])"), "[해시 가림]"),
    ("주민등록번호", re.compile(r"\b\d{6}-[1-4]\d{6}\b"), "******-*******"),
    ("전화번호", re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"), "010-****-****"),
    ("이메일", re.compile(r"\b([A-Za-z0-9._%+-]{3,})@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b"), _email),
]

# 가리지 않는 속성(ID·선택 값·링크·날짜)
SKIP_PROPS = re.compile(r"(ID$|^자산$|^버전$|일$|링크$|^출처$|^CWE$|^검토자$|^작성자$)")
# 가리지 않는 DB: 자산(P2)은 호스트·IP가 보고서에 그대로 필요함
SKIP_DBS = ("P2",)


def mask_text(text: str) -> tuple[str, Counter]:
    hits: Counter = Counter()
    if not text:
        return text, hits
    for name, pat, repl in RULES:
        text, n = pat.subn(repl, text)
        if n:
            hits[name] += n
    return text, hits


def apply(pages: list[Page]) -> list[dict]:
    """모든 페이지의 글·코드·표·속성을 가리고, 가린 내용을 검토 목록용 경고로 돌려줌."""
    issues = []
    shots = 0
    for p in pages:
        if p.db in SKIP_DBS:
            continue
        total: Counter = Counter()
        for k, v in list(p.props.items()):
            if isinstance(v, str) and not SKIP_PROPS.search(k):
                p.props[k], h = mask_text(v)
                total += h
        for b in p.blocks:
            if b.type == "image":
                shots += 1
                continue
            b.text, h = mask_text(b.text)
            total += h
            for r in b.rows:
                for c, cell in enumerate(r):
                    r[c], h = mask_text(cell)
                    total += h
        p.props["마스킹 완료"] = "Yes"
        if total:
            where = p.prop("건 ID") or p.prop("단계 ID") or p.prop("취약점 ID") or p.prop("시나리오 ID") or p.title
            what = ", ".join(f"{k} {n}곳" for k, n in total.items())
            issues.append({"level": "warning", "rule": "자동 마스킹", "where": f"{p.db} {where}",
                           "msg": f"자동으로 가림: {what}. 빠진 값이 없는지 본문을 한 번 확인"})
    if shots:
        issues.append({"level": "warning", "rule": "자동 마스킹", "where": "스크린샷",
                       "msg": f"그림 {shots}개는 자동으로 가리지 못함. 그림 속 토큰·계정·식별자를 직접 확인"})
    return issues
