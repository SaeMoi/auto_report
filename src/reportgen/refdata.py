"""reference/ 와 docs/REPORT_STYLE.md 의 기준 데이터를 읽음."""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from .config import TOOL_ROOT, load_yaml

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "info": "Info"}
SEVERITY_RANGE = {"critical": (9.0, 10.0), "high": (7.0, 8.9), "medium": (4.0, 6.9), "low": (0.1, 3.9), "info": (0.0, 0.0)}

ZONE_LABEL = {"external_dmz": "외부(DMZ)", "internal_admin": "관리·내부"}
CHECK_LABEL = {"good": "양호", "vulnerable": "취약", "na": "-"}
STATUS_LABEL = {"open": "미조치", "fixed": "조치 완료", "partial": "부분 조치", "verified": "재검증 완료"}
FIX_PRIORITY_LABEL = {"immediate": "즉시", "short": "단기", "mid": "중기"}
OBJ_TYPE_LABEL = {"primary": "1차", "secondary": "2차"}
OBJ_STATUS_LABEL = {"achieved": "달성", "partial": "부분 달성", "not_achieved": "미달성"}
START_COND_LABEL = {"external": "외부 공격자", "member": "회원 계정", "assumed_breach": "침해 가정"}
OUTCOME_LABEL = {"blocked": "차단", "detected": "탐지", "not_detected": "미탐", "invalid": "검증 무효"}
GAP_LABEL = {"visibility": "가시성", "detection_logic": "탐지 로직", "alert_suppression": "경보 억제",
             "process": "프로세스", "timeliness": "적시성", "invalid": "검증 무효", "none": "-"}
PATCH_TYPE_LABEL = {"code": "코드 수정", "config": "설정 변경", "removal": "기능 제거", "temporary": "임시 차단"}
SOURCE_LABEL = {"scenario_step": "시나리오 단계", "finding_instance": "취약점 건", "attack_emulation": "ATT&CK 모사"}


def sev_rank(sev: str | None) -> int:
    return SEVERITY_ORDER.index(sev) if sev in SEVERITY_ORDER else len(SEVERITY_ORDER)


def severity_for_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score == 0:
        return "info"
    for sev, (lo, hi) in SEVERITY_RANGE.items():
        if lo <= score <= hi + 0.05:
            return sev
    return None


@lru_cache
def owasp() -> dict:
    data = load_yaml(TOOL_ROOT / "reference" / "owasp_2025.yaml")
    return {c["code"]: c for c in data.get("categories", [])}


def owasp_label(code: str | None) -> str:
    c = owasp().get(code or "")
    return f"{code} {c['name']}" if c else (code or "")


def owasp_item(code: str, title: str) -> dict | None:
    for item in owasp().get(code, {}).get("items", []):
        if item["title"] == title:
            return item
    return None


@lru_cache
def ptef() -> dict:
    return load_yaml(TOOL_ROOT / "reference" / "ptef_scores.yaml")


@lru_cache
def style() -> dict:
    """REPORT_STYLE.md 의 기계 판독 YAML 블록과 사람용 본문(프롬프트 삽입용 요약)."""
    text = (TOOL_ROOT / "docs" / "REPORT_STYLE.md").read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    data = yaml.safe_load(m.group(1)) if m else {}
    rules = []
    for line in text.splitlines():
        m2 = re.match(r"\|\s*(ST-\d+a?)\s*\|\s*(.+?)\s*\|", line)
        if m2:
            rules.append(f"- {m2.group(1)}: {m2.group(2)}")
    data["_rules_text"] = "\n".join(rules)
    return data


STEP_STATUS_LABEL = {"success": "확인", "failed": "실패", "untested": "미시험"}
TIME_BASIS_LABEL = {"log": "로그", "screen": "화면", "estimate": "추정", "unknown": "확인 필요"}
TECH_RE = re.compile(r"\b(T\d{4})(\.\d{3})?\b")


@lru_cache
def attack() -> dict:
    return load_yaml(TOOL_ROOT / "reference" / "attack_tactics.yaml")


def attack_tactic(technique: str | None, tactic: str | None = None) -> dict | None:
    """단계의 「ATT&CK 기법」(예: 「T1059.004 Command … [검증 요]」)과 선택 칸 「전술」 → 전술 {id, ko, en, order}.

    「전술」 칸 값(한글·영문·TA 번호)을 먼저 보고, 없으면 기법 번호로 찾음. 못 찾으면 None."""
    data = attack()
    tactics = data.get("tactics", [])
    if tactic and tactic.strip():
        t = tactic.strip().lower()
        for n, x in enumerate(tactics):
            if t in (x["id"].lower(), x["ko"], x["en"].lower()):
                return dict(x, order=n)
    m = TECH_RE.search(technique or "")
    if not m:
        return None
    ta = (data.get("techniques") or {}).get(m.group(1))
    for n, x in enumerate(tactics):
        if x["id"] == ta:
            return dict(x, order=n)
    return None


def attack_id(technique: str | None) -> str:
    """「T1059.004 Command … [검증 요]」 → 「T1059.004」. 번호가 없으면 원문."""
    m = TECH_RE.search(technique or "")
    return m.group(0) if m else (technique or "")
