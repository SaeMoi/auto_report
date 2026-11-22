"""출력 전 검사(2026-11-16 블루팀 피드백). 보고서 Markdown을 만든 직후, DOCX·PDF로 내보내기 전에 돎.

점수·시각·건수가 서로 맞는지, 본문이 참조한 룰 전문이 부록에 있는지, 대기 문구가 남았는지를 봄.
- error: 최종본(--draft 없음)은 만들지 않음. 초안은 만들되 목록을 남김
- warning: 만들되 목록에 남김
결과는 work/<보고서>/output_check.md 에 씀.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ..dtutil import parse_dt

PLACEHOLDERS = ("[확인 필요]", "[AI 작업 대기]")
CUSTOM_RULE_MIN = 100000
RULE_ID_IN_XML = re.compile(r"<rule\b[^>]*\bid=\"(\d+)\"")


def _e(rule: str, where: str, msg: str) -> dict:
    return {"level": "error", "rule": rule, "where": where, "msg": msg}


def _w(rule: str, where: str, msg: str) -> dict:
    return {"level": "warning", "rule": rule, "where": where, "msg": msg}


def _dt(s):
    return parse_dt(s)   # 시간대 없는 값은 KST(dtutil)


def rule_refs(blue: dict) -> tuple[list[int], set[int]]:
    """(본문이 참조한 커스텀 룰 번호, 부록 A에 전문이 있는 룰 번호)."""
    refs: set[int] = set()
    for fx in blue.get("detection_fixes", []):
        refs |= set(fx.get("rule_ids") or [])
    for t in blue.get("test_cases", []):
        refs |= {a["rule_id"] for a in t.get("alerts", []) if a.get("rule_id")}
    for ls in blue.get("log_sources", []):
        refs |= set(ls.get("rule_ids") or [])
    for m in blue.get("modules", []):
        refs |= set(m.get("ar_trigger_rule_ids") or [])
    refs = {r for r in refs if isinstance(r, int) and r >= CUSTOM_RULE_MIN}
    have = {int(x) for fx in blue.get("detection_fixes", []) for x in RULE_ID_IN_XML.findall(fx.get("rule_source") or "")}
    have |= {c["rule_id"] for c in blue.get("rule_catalog", []) or [] if c.get("xml")}
    return sorted(refs), have


def check_blue(data: dict) -> list[dict]:
    out: list[dict] = []
    p = data.get("project") or {}
    b = data.get("blue") or {}
    tests = [t for t in b.get("test_cases", []) if t.get("status") == "executed"]
    by_id = {t["test_id"]: t for t in tests}
    min_level = (b.get("response_procedure") or {}).get("min_level")

    # O-01 점수 4 이상(경보를 확인·판단)인데 8-1 확인 시각이 없음 / O-02 알림 기준보다 낮은 룰로 4점 이상
    def score_checks(tid: str, score, where: str, ack_at=None, rule_level=None):
        t = by_id.get(tid) or {}
        if score is None or score < 4:
            return
        if not (ack_at or (t.get("triage") or {}).get("ack_at")):
            out.append(_e("O-01", where, f"{tid} 점수 {score}점인데 8-1 「확인 시각」이 없음(4점은 블루팀 확인·판단 기록이 근거). "
                                         "B4 「확인 시각(초)」(재검증은 B5 「재검증 확인 시각(초)」)을 채우거나 3점으로 내림"))
        levels = ([rule_level] if rule_level is not None else
                  [a.get("level") for a in t.get("alerts", []) if a.get("level") is not None])
        if min_level and levels and max(levels) < min_level:
            out.append(_w("O-02", where, f"{tid} 경보 level {max(levels)}이 알림 기준 {min_level}보다 낮아 알림이 가지 않는데 "
                                         f"{score}점임(3점 이하가 맞는지 확인)"))
        if score == 5 and rule_level is None and not (t.get("triage") or {}).get("resolved_at"):
            out.append(_w("O-03", where, f"{tid} 5점(차단)인데 차단 실행 기록(조치 완료 시각·active-responses.log)이 없음"))

    for t in tests:
        score_checks(t["test_id"], t.get("score"), t["test_id"])
    for fx in b.get("detection_fixes", []):
        rt = fx.get("retest") or {}
        for tid in fx.get("test_ids", []):
            where = f"{fx['fix_id']} 재검증 {tid}"
            score_checks(tid, rt.get("score_after"), where, ack_at=rt.get("ack_at"),
                         rule_level=(fx.get("priority") or {}).get("level"))
            t = by_id.get(tid) or {}
            a, e = _dt(rt.get("at")), _dt(t.get("executed_at"))
            if rt.get("score_after") is not None or rt.get("outcome_after"):
                if not rt.get("at"):
                    out.append(_w("O-04", where, "재검증 결과가 있는데 재검증 시각이 없음(팀 기록 없음으로 표기)"))
                elif a and e and a <= e:
                    out.append(_e("O-04", where, f"재검증 시각({rt['at']})이 최초 실행 시각({t.get('executed_at')})보다 뒤가 아님. "
                                                 "같은 공격을 다시 수행한 시각을 적어야 함"))
                if not rt.get("evidence_ids"):
                    out.append(_w("O-05", where, "재검증 증거가 없음(B5 「재검증 증거」)"))

    # O-06 공백 건수 합 = 미탐·부분 탐지 건수, 개선 과제·전략서의 공백 유형이 1-3에 있는지
    misses = [t for t in tests if t.get("outcome") != "invalid"
              and (t.get("outcome") == "not_detected" or (t.get("score") is not None and t["score"] < 3))]
    gaps = Counter(t.get("gap") for t in tests if t.get("gap") and t.get("gap") != "none")
    if sum(gaps.values()) != len(misses):
        out.append(_e("O-06", "1-3", f"공백 건수 합({sum(gaps.values())})이 미탐·3점 미만 건수({len(misses)})와 다름"))
    for t in misses:
        if not t.get("gap") or t.get("gap") == "none":
            out.append(_e("O-06", t["test_id"], "미탐·3점 미만인데 공백 유형이 없음"))
    for fx in b.get("detection_fixes", []):
        g = (fx.get("categorization") or {}).get("gap")
        if g and g != "none" and not gaps.get(g):
            out.append(_e("O-06", fx["fix_id"], f"전략서 공백 유형 「{g}」이 1-3 표에서 0건임(테스트 케이스 공백과 맞춤)"))
    for task in b.get("improvement_tasks", []) or []:
        g = task.get("gap")
        if g and g != "none" and not gaps.get(g):
            out.append(_w("O-06", task.get("title", "개선 과제"), f"개선 과제의 공백 유형 「{g}」이 1-3 표에서 0건임"))

    # O-07 MTTD가 0초인데 NTP 확인 기록 없음
    lat = [t.get("latency_sec") for t in tests if t.get("latency_sec") is not None]
    vc = b.get("verification_conditions") or {}
    if lat and not vc.get("ntp_checked"):
        if max(lat) <= 1:
            out.append(_w("O-07", "8-2", "MTTD가 0~1초인데 NTP 확인 기록이 없음. 시각 동기화 확인을 남기거나 값의 한계를 적음"))

    # O-08 본문이 참조한 커스텀 룰의 전문이 부록 A에 있는지
    refs, have = rule_refs(b)
    missing = [r for r in refs if r not in have]
    if missing:   # 2026-11-21: 팀 기록에 XML이 없으면 채울 수 없음 → 요약표로 대신하고 경고만
        cat = {c["rule_id"] for c in b.get("rule_catalog", []) or []}
        summ = [r for r in missing if r in cat]
        none = [r for r in missing if r not in cat]
        msg = f"본문이 참조한 룰 {len(missing)}개의 XML 전문이 없음. 팀 룰 표 요약으로 실음 {len(summ)}개"
        if none:
            msg += f", 요약도 없음 {len(none)}개: {', '.join(map(str, none))}"
        out.append(_w("O-08", "부록 A", msg))

    # O-09 탐지된 케이스인데 경보 rule.id가 없음
    for t in tests:
        if t.get("outcome") in ("detected", "blocked") and not any(a.get("rule_id") for a in t.get("alerts", [])):
            out.append(_e("O-09", t["test_id"], "탐지·차단인데 경보 표에 rule.id가 없음"))

    # O-13 자산 ID·구역·에이전트가 서로 맞는지(로그 소스 에이전트 서버 = 그 자산의 서버)
    from ..build.assets import mismatches
    for x in mismatches(data):
        hint = f"자산을 {x['suggest']}로 바꾸거나" if x.get("suggest") else "자산 ID를 고치거나"
        out.append(_w("O-13", f"2-2 {x['source']}", f"{x['asset_id']}의 서버는 {x['asset_server']}인데 에이전트가 {x['agent']}임. "
                                                   f"앞단 프록시(DMZ nginx)에 로그가 쌓이는 구성이면 그대로 둬도 됨. 아니면 B2 로그 소스의 {hint} P2 자산의 호스트를 고침"))

    # O-10 문서 정보 빈칸
    for key, label in (("authors", "작성자"), ("revisions", "개정 이력")):
        if not p.get(key):
            out.append(_w("O-10", "P1", f"「{label}」이 비어 있음"))
    if not (p.get("period") or {}).get("start"):
        out.append(_w("O-10", "P1", "「수행 기간」이 비어 있음"))
    return out


def check_markdown(md: str) -> list[dict]:
    out = []
    for ph in PLACEHOLDERS:
        n = md.count(ph)
        if n:
            out.append(_e("O-11", "본문", f"「{ph}」 {n}개가 남아 있음"))
    # 자동 링크로 바뀐 파일·필드 이름이 남았는지([x](http://x))
    n = len(re.findall(r"\[([^\]]+)\]\(https?://\1/?\)", md))
    if n:
        out.append(_w("O-12", "본문", f"자동 링크로 바뀐 이름 {n}개(노션 원문 확인)"))
    return out


def run(report: str, data: dict, md: str) -> list[dict]:
    out = check_markdown(md)
    if report == "blue":
        out = check_blue(data) + out
    return out


def write(path: Path, issues: list[dict], draft: bool) -> None:
    errs = [i for i in issues if i["level"] == "error"]
    lines = ["# 출력 전 검사", "",
             f"- 오류 {len(errs)}건, 경고 {len(issues) - len(errs)}건",
             "- 오류가 있으면 최종본은 만들지 않음" + ("(이번은 초안이라 만듦)" if draft else ""), "",
             "| 수준 | 규칙 | 위치 | 내용 |", "| --- | --- | --- | --- |"]
    for i in issues:
        lines.append(f"| {'오류' if i['level'] == 'error' else '경고'} | {i['rule']} | {i['where']} | "
                     f"{i['msg'].replace('|', '/')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
