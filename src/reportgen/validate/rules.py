"""검증 규칙 R-01~R-28(규격서 v0.3 6장, R-28은 2026-11-18 모의해킹 보고서용).

각 함수는 issue 목록을 돌려줌: {"level": "error"|"warning", "rule": "R-NN", "where": "<ID>", "msg": "..."}
- intake 범위: R-01~R-13, R-16, R-19~R-26 (데이터만 보면 되는 규칙)
- AI 결과 범위: R-14, R-15, R-17, R-27 (ai/check.py에서 실행)
- 발행 직전: R-18 (needs_review 0건)
"""
from __future__ import annotations

import re

from jsonschema import Draft202012Validator

from .. import refdata
from ..build import cvss
from ..config import TOOL_ROOT
from ..dtutil import parse_dt

import json

_SCHEMA = None


def _schema() -> dict:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads((TOOL_ROOT / "schema" / "report.schema.json").read_text(encoding="utf-8"))
    return _SCHEMA


def E(rule: str, where: str, msg: str) -> dict:
    return {"level": "error", "rule": rule, "where": where, "msg": msg}


def W(rule: str, where: str, msg: str) -> dict:
    return {"level": "warning", "rule": rule, "where": where, "msg": msg}


ID_PATTERNS = {
    "asset_id": r"^A-\d{2}$", "finding_id": r"^V-\d{2}$", "instance_id": r"^V-\d{2}-\d+$",
    "scenario_id": r"^S\d+$", "step_id": r"^S\d+-STEP\d+$", "test_id": r"^D-\d{2}$", "fix_id": r"^F-\d{2}$",
    "objective_id": r"^O-\d+$", "evidence_id": r"^E-\d{3}$", "patch_id": r"^P-\d{2}$",
}

MASK_PATTERNS = [
    (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT"),
    (r"(?i)(password|passwd|pwd|secret|api[_-]?key)\s*[=:]\s*[\"']?(?!\*)[^\s\"'&*]{4,}", "비밀번호·키"),
    (r"\b\d{6}-[1-4]\d{6}\b", "주민등록번호"),
    (r"\b01[016789]-?\d{3,4}-?\d{4}\b", "전화번호"),
    (r"(?i)authorization:\s*bearer\s+(?!\*)[A-Za-z0-9._-]{16,}", "Authorization 헤더"),
    (r"(?i)(JSESSIONID|session|sid)=(?!\*)[A-Za-z0-9]{16,}", "세션 값"),
]


# ── R-01, R-02 스키마·열거형 ─────────────────────────────────────
def r01_schema(data: dict) -> list[dict]:
    out = []
    v = Draft202012Validator(_schema())
    for err in sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(x) for x in err.absolute_path)
        rule = "R-02" if err.validator == "enum" else ("R-04" if err.validator == "pattern" else "R-01")
        out.append(E(rule, _where(data, err.absolute_path) or path, f"{path}: {err.message}"))
    return out


def _where(data: dict, path) -> str:
    """스키마 오류 위치를 사람이 찾을 수 있는 ID로."""
    node = data
    label = ""
    for p in path:
        try:
            node = node[p]
        except (KeyError, IndexError, TypeError):
            break
        if isinstance(node, dict):
            for k in ("instance_id", "finding_id", "step_id", "scenario_id", "test_id", "fix_id", "asset_id",
                      "objective_id", "evidence_id", "patch_id", "code"):
                if node.get(k):
                    label = node[k]
                    break
    return label


# ── R-03, R-04 참조·ID ───────────────────────────────────────────
def r03_r04_ids(data: dict) -> list[dict]:
    out = []
    sets: dict[str, set] = {}

    def reg(kind: str, items: list[dict]):
        s = sets.setdefault(kind, set())
        for it in items:
            i = it.get(kind)
            if not i:
                continue
            if i in s:
                out.append(E("R-04", i, f"ID 중복: {i}"))
            s.add(i)

    reg("asset_id", data.get("assets", []))
    reg("objective_id", data.get("objectives", []))
    reg("finding_id", data.get("findings", []))
    reg("instance_id", data.get("instances", []))
    reg("scenario_id", data.get("scenarios", []))
    steps = [s for sc in data.get("scenarios", []) for s in sc.get("steps", [])]
    reg("step_id", steps)
    reg("evidence_id", data.get("evidence", []))
    blue = data.get("blue") or {}
    reg("test_id", blue.get("test_cases", []))
    reg("fix_id", blue.get("detection_fixes", []))
    A, F, I, S, T, X, O = (sets.get(k, set()) for k in
                           ("asset_id", "finding_id", "instance_id", "step_id", "test_id", "fix_id", "objective_id"))
    SC = sets.get("scenario_id", set())

    def chk(where: str, ids, pool: set, what: str, optional_pool: bool = False):
        if optional_pool and not pool:
            return
        for x in ids or []:
            if x and x not in pool:
                out.append(E("R-03", where, f"{what} {x}이(가) 없음"))

    for i in data.get("instances", []):
        chk(i["instance_id"], [i.get("finding_id")], F, "취약점")
        chk(i["instance_id"], [i.get("asset_id")], A, "자산")
        chk(i["instance_id"], i.get("step_ids"), S, "시나리오 단계")
        chk(i["instance_id"], i.get("test_ids"), T, "테스트", optional_pool=True)
    for f in data.get("findings", []):
        if f["finding_id"] not in {i["finding_id"] for i in data.get("instances", [])}:
            out.append(W("R-03", f["finding_id"], "건(R1)이 하나도 없는 취약점"))
    for sc in data.get("scenarios", []):
        chk(sc["scenario_id"], sc.get("objective_ids"), O, "목표")
        for s in sc.get("steps", []):
            chk(s["step_id"], [s.get("asset_id")], A, "자산")
            chk(s["step_id"], s.get("instance_ids"), I, "취약점 건")
    for o in data.get("objectives", []):
        chk(o["objective_id"], o.get("scenario_ids"), SC, "시나리오", optional_pool=not data.get("scenarios"))
    for p in data.get("patches", []):
        chk(p["patch_id"], p.get("instance_ids"), I, "취약점 건")
    for r in data.get("retests", []):
        chk("R7 " + r["instance_id"], [r["instance_id"]], I, "취약점 건")
    for t in blue.get("test_cases", []):
        if t.get("source") == "scenario_step" and data.get("scenarios"):
            chk(t["test_id"], [t.get("source_ref")], S, "시나리오 단계")
        if t.get("source") == "finding_instance" and data.get("instances"):
            chk(t["test_id"], [t.get("source_ref")], I, "취약점 건")
        chk(t["test_id"], t.get("fix_ids"), X, "개선 조치")
    for fx in blue.get("detection_fixes", []):
        chk(fx["fix_id"], fx.get("test_ids"), T, "테스트")
    for k, pat in ID_PATTERNS.items():
        for x in sets.get(k, set()):
            if not re.match(pat, x):
                out.append(E("R-04", x, f"ID 형식이 {pat}와 다름"))
    return out


# ── R-05 범위 ────────────────────────────────────────────────────
def r05_scope(data: dict) -> list[dict]:
    assets = {a["asset_id"]: a for a in data.get("assets", [])}
    out = []
    for i in data.get("instances", []):
        a = assets.get(i.get("asset_id"))
        if a and a.get("scope") not in ("in_scope", "out_of_scope"):
            out.append(E("R-05", i["instance_id"], f"자산 {a['asset_id']}의 범위가 비어 있음"))
    return out


# ── R-06 CVSS ────────────────────────────────────────────────────
def r06_cvss(data: dict) -> list[dict]:
    out = []
    for i in data.get("instances", []):
        c = i.get("cvss") or {}
        w = i["instance_id"]
        if not c.get("vector") or c.get("score") is None:
            out.append(W("R-06", w, "CVSS 점수 또는 벡터가 비어 있음"))
            continue
        calc = cvss.base_score(c["vector"])
        if calc is None:
            out.append(W("R-06", w, f"CVSS 벡터를 해석할 수 없음: {c['vector']}"))
        elif abs(calc - float(c["score"])) > 0.05:
            out.append(W("R-06", w, f"벡터로 다시 계산한 점수 {calc}와 적힌 점수 {c['score']}가 다름"))
        band = refdata.severity_for_score(float(c["score"]))
        if band and i.get("severity") and band != i["severity"]:
            out.append(W("R-06", w, f"점수 {c['score']}는 {refdata.SEVERITY_LABEL[band]} 구간인데 위험도는 "
                                    f"{refdata.SEVERITY_LABEL.get(i['severity'], i['severity'])}임(값은 바꾸지 않음)"))
    return out


# ── R-07 제목 단일 출처 ──────────────────────────────────────────
def r07_titles(data: dict) -> list[dict]:
    out = []
    for f in data.get("findings", []):
        if not (f.get("title") or "").strip():
            out.append(E("R-07", f["finding_id"], "취약점명(R2 제목)이 비어 있음"))
    return out


# ── R-10 공백 ────────────────────────────────────────────────────
def r10_gap(data: dict) -> list[dict]:
    out = []
    for t in (data.get("blue") or {}).get("test_cases", []):
        if t.get("status") != "executed" or t.get("outcome") == "invalid":
            continue
        if (t.get("outcome") == "not_detected" or (t.get("score") is not None and t["score"] < 3)) and \
                (not t.get("gap") or t["gap"] == "none"):
            out.append(E("R-10", t["test_id"], "미탐 또는 3점 미만인데 「공백」이 비어 있음"))
    return out


# ── R-11, R-12 마스킹 ────────────────────────────────────────────
def r11_r12_mask(data: dict) -> list[dict]:
    out = []
    for e in data.get("evidence", []):
        if not e.get("masked"):
            out.append(E("R-11", e["owner_id"], f"{e['evidence_id']}: 페이지의 「마스킹 완료」가 꺼져 있어 보고서에 넣지 않음"))
    texts = []
    for i in data.get("instances", []):
        poc = i.get("poc") or {}
        texts += [(i["instance_id"], poc.get("request", "")), (i["instance_id"], poc.get("response", "")),
                  (i["instance_id"], i.get("diff", ""))]
    for sc in data.get("scenarios", []):
        for s in sc.get("steps", []):
            texts += [(s["step_id"], a) for a in s.get("actions", [])]
    for e in data.get("evidence", []):
        if e.get("kind") != "screenshot" and e.get("path", "").endswith(".txt"):
            try:
                from pathlib import Path

                texts.append((e["owner_id"], Path(e["path"]).read_text(encoding="utf-8")))
            except OSError:
                pass
    for where, t in texts:
        for pat, label in MASK_PATTERNS:
            if t and re.search(pat, t):
                out.append(E("R-12", where, f"마스킹되지 않은 {label}로 보이는 값이 있음"))
                break
    return out


# ── R-13 OWASP·CWE ───────────────────────────────────────────────
def r13_codes(data: dict) -> list[dict]:
    out = []
    codes = set(refdata.owasp())
    for f in data.get("findings", []):
        if f.get("owasp_2025") not in codes:
            out.append(E("R-13", f["finding_id"], f"취약점 유형 {f.get('owasp_2025')}이 A01~A10이 아님"))
        for c in f.get("cwe", []):
            if not re.match(r"^CWE-\d+$", c):
                out.append(E("R-13", f["finding_id"], f"CWE 형식 오류: {c}"))
    for c in data.get("check_items", []):
        if c.get("code") not in codes:
            out.append(E("R-13", c.get("name", "?"), f"진단 항목 코드 {c.get('code')}이 A01~A10이 아님"))
    return out


# ── R-16 시각 ────────────────────────────────────────────────────
TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$")


def r16_time(data: dict) -> list[dict]:
    out = []
    for sc in data.get("scenarios", []):
        for s in sc.get("steps", []):
            for k in ("start_at", "end_at"):
                if s.get(k) and not TS.match(s[k]):
                    out.append(W("R-16", s["step_id"], f"{k} 형식이 ISO 8601 +09:00이 아님: {s[k]}"))
            try:
                if parse_dt(s["end_at"]) < parse_dt(s["start_at"]):
                    out.append(W("R-16", s["step_id"], "종료 시각이 시작 시각보다 빠름"))
            except (KeyError, TypeError, ValueError):
                pass
    for t in (data.get("blue") or {}).get("test_cases", []):
        if t.get("executed_at") and not TS.match(t["executed_at"]):
            out.append(W("R-16", t["test_id"], f"실행 시각 형식 오류: {t['executed_at']}"))
    return out


# ── R-19, R-20, R-21, R-22 블루팀 ───────────────────────────────
def r19_r22_blue(data: dict) -> list[dict]:
    out = []
    proj = data.get("project") or {}
    blue = data.get("blue") or {}
    if proj.get("report_type") == "blue" and proj.get("version") not in ("0.5", "1.0"):
        out.append(E("R-19", "P1", f"블루팀 보고서 버전은 0.5 또는 1.0이어야 함({proj.get('version')})"))
    steps = {s["step_id"]: s for sc in data.get("scenarios", []) for s in sc.get("steps", [])}
    for t in blue.get("test_cases", []):
        if t.get("status") == "executed":
            for k, label in (("executed_at", "실행 시각(초)"), ("source_ip", "출발지 IP"), ("outcome", "결과 분류")):
                if not t.get(k):
                    out.append(E("R-20", t["test_id"], f"실행 완료인데 「{label}」이 비어 있음"))
            if t.get("outcome") != "invalid" and t.get("score") is None:
                out.append(E("R-20", t["test_id"], "실행 완료인데 「점수」가 비어 있음"))
        elif proj.get("report_type") == "blue" and proj.get("version") == "1.0":
            out.append(E("R-20", t["test_id"], "v1.0 발행인데 「계획」 상태 테스트가 남아 있음"))
        if t.get("source") == "scenario_step" and t.get("source_ref") in steps and t.get("executed_at"):
            s = steps[t["source_ref"]]
            try:
                ok_time = (parse_dt(s["start_at"]) <= parse_dt(t["executed_at"]) <= parse_dt(s["end_at"]))
            except (KeyError, TypeError, ValueError):
                ok_time = True
            if not ok_time:
                out.append(W("R-21", t["test_id"], f"실행 시각이 {s['step_id']} 시각 범위 밖임(출처 연결 확인)"))
            if t.get("source_ip") and s.get("source_ip") and t["source_ip"] != s["source_ip"]:
                out.append(W("R-21", t["test_id"], f"출발지 IP가 {s['step_id']}와 다름"))
    if proj.get("report_type") == "pentest":   # 2026-11-22 옛 결과 보고서(result) 대신 시나리오를 싣는 모의해킹 보고서에 적용
        n = sum(1 for s in steps.values() if not s.get("actual_detection"))
        if n:
            out.append(W("R-22", "시나리오 단계", f"블루팀 검증 전 단계 {n}개(v1.1에서 반영, 발행 차단 안 함)"))
    return out


# ── R-23 ~ R-26 ──────────────────────────────────────────────────
def r23_check_consistency(data: dict) -> list[dict]:
    out = []
    for c in data.get("check_items", []):
        for r in c.get("results", []):
            n = len(r.get("instance_ids", []))
            w = f"{c.get('code')} {r['asset_id']}"
            if n and r["result"] in ("good", "na"):
                out.append(E("R-23", w, f"건 {n}개가 있는데 판정이 {refdata.CHECK_LABEL[r['result']]}임"))
            if not n and r["result"] == "vulnerable":
                out.append(W("R-23", w, "판정이 취약인데 해당 건이 없음"))
        if c.get("checked_items_default"):
            out.append(W("R-23", c.get("code", "?"), "R3 「점검 취약점」이 비어 있어 범주의 모든 취약점을 표에 넣었음"))
    return out


POC_LABEL = {"location": "위치", "steps": "재현 과정", "request": "공격 요청", "explanation": "공격 설명",
             "response": "결과"}


def r24_detail(data: dict) -> list[dict]:
    out = []
    by_f: dict[str, list[dict]] = {}
    for i in data.get("instances", []):
        by_f.setdefault(i["finding_id"], []).append(i)
    sev = {f["finding_id"]: f for f in data.get("findings", [])}
    for fid, its in by_f.items():
        low = (sev.get(fid) or {}).get("severity") in ("low", "info")
        if not any(i["instance_id"].endswith("-1") for i in its):
            out.append(E("R-24", fid, "대표 건(V-NN-1)이 없음"))
        for i in its:
            if i["instance_id"].endswith("-1"):
                poc = i.get("poc") or {}
                need = ["location"] if low else list(POC_LABEL)
                for k in need:
                    v = poc.get(k)
                    if k == "response" and not v and poc.get("result_facts"):
                        continue
                    if k == "request" and not v and poc.get("request_figs"):   # 패킷 화면으로 대신함
                        continue
                    if not v:
                        out.append(E("R-24", i["instance_id"], f"{POC_LABEL[k]} 없음"))
            elif not (i.get("diff") or "").strip():
                out.append(E("R-24", i["instance_id"], "「대표 건과 다른 점」 없음"))
    return out


def r25_flags(data: dict) -> list[dict]:
    out = []
    for f in data.get("findings", []):
        if f.get("classification") == "needs_check":
            out.append(W("R-25", f["finding_id"], "분류 확정이 「확인 필요」임"))
        has_code = (f.get("remediation") or {}).get("code_after") or (f.get("remediation") or {}).get("code_before")
        if has_code and not f.get("code_reviewed"):
            out.append(W("R-25", f["finding_id"], "코드 예시를 사람이 확인하지 않음(코드 검토 완료 꺼짐)"))
        if not f.get("fix_priority") and (data.get("project") or {}).get("report_type") == "diag":
            out.append(E("R-25", f["finding_id"], "「조치 구분」이 비어 있음(v0.5부터 필수)"))
    findings = {f["finding_id"]: f for f in data.get("findings", [])}
    for i in data.get("instances", []):
        if (findings.get(i["finding_id"]) or {}).get("owasp_2025") == "A03" and not i.get("cve_ids"):
            if not re.search(r"CVE-\d{4}-\d+", json.dumps(i, ensure_ascii=False)):
                out.append(W("R-25", i["instance_id"], "A03 건인데 CVE 번호가 없음"))
    for sc in data.get("scenarios", []):
        for s in sc.get("steps", []):
            r = s.get("result") or {}
            if r.get("status") == "failed" and not r.get("blocked_reason"):
                out.append(W("R-25", s["step_id"], "실패 단계인데 「막힌 이유」가 비어 있음"))
            if r.get("status") == "success" and not r.get("gained"):
                out.append(W("R-25", s["step_id"], "확인 단계인데 「획득한 것」이 비어 있음"))
    return out


# 대상에 남긴 영향이 이 말로 끝나면 정리할 것이 없음
NO_TRACE_RE = re.compile(r"(읽기만|조회만|요청 로그만|쓰지 않음|바꾸지 않음|변경 없음|없음|^-$)")


def r28_pentest(data: dict) -> list[dict]:
    """모의해킹 보고서 입력 점검(2026-11-18): 시각 근거·ATT&CK 전술·정리 내역. 모두 경고."""
    from .. import refdata
    out = []
    for sc in data.get("scenarios", []):
        scid = sc["scenario_id"]
        for s in sc.get("steps", []):
            st = (s.get("result") or {}).get("status")
            if st == "untested":
                continue
            if not s.get("start_at") or "T" not in s.get("start_at", ""):
                out.append(W("R-28", s["step_id"], "시작 시각이 없거나 날짜만 있음(블루팀 대조에는 분 단위 시각이 필요함)"))
            elif s.get("time_basis") in ("", "unknown"):
                out.append(W("R-28", s["step_id"], "「시각 근거」가 비었거나 확인 필요임"))
            if s.get("attack_technique") and not refdata.attack_tactic(s.get("attack_technique"), s.get("tactic")):
                out.append(W("R-28", s["step_id"], f"ATT&CK 기법 「{s['attack_technique']}」의 전술을 찾지 못함(「전술」 칸에 적어 주세요)"))
            if "검증 요" in (s.get("attack_technique") or ""):
                out.append(W("R-28", s["step_id"], "ATT&CK 기법이 「검증 요」임"))
        left = [s for s in sc.get("steps", []) if s.get("target_impact") and not NO_TRACE_RE.search(s["target_impact"])]
        if left and not sc.get("cleanup"):
            out.append(W("R-28", scid, "대상에 흔적을 남긴 단계가 있는데 본문 「정리 내역」 표가 비어 있음: "
                                         + ", ".join(s["step_id"] for s in left)))
        for c in sc.get("cleanup", []):
            if not c.get("done") or "확인 필요" in c["done"]:
                out.append(W("R-28", scid, f"정리 내역 「{c['item']}」의 정리 여부가 비었거나 확인 필요임"))
    return out


def r26_representative(data: dict) -> list[dict]:
    out = []
    by_f: dict[str, list[dict]] = {}
    for i in data.get("instances", []):
        by_f.setdefault(i["finding_id"], []).append(i)
    for fid, its in by_f.items():
        rep = next((i for i in its if i["instance_id"].endswith("-1")), None)
        best = min((i.get("severity") for i in its), key=refdata.sev_rank, default=None)
        if rep and best and refdata.sev_rank(rep.get("severity")) > refdata.sev_rank(best):
            out.append(W("R-26", rep["instance_id"], f"대표 건 위험도가 같은 취약점의 최고 등급({refdata.SEVERITY_LABEL[best]})보다 낮음. "
                                                     "최고 등급 건을 1번으로 바꾸는 것을 권장함"))
    return out


INTAKE_RULES = [r01_schema, r03_r04_ids, r05_scope, r06_cvss, r07_titles, r10_gap, r11_r12_mask, r13_codes, r16_time,
                r19_r22_blue, r23_check_consistency, r24_detail, r25_flags, r26_representative, r28_pentest]


def run_intake(data: dict, report: str | None = None) -> list[dict]:
    out = []
    for rule in INTAKE_RULES:
        try:
            out += rule(data)
        except Exception as ex:  # 규칙 하나가 깨져도 나머지는 실행
            out.append(W("R-00", rule.__name__, f"검사 중 오류: {ex}"))
    if report in ("blue", "pentest"):   # 블루팀·모의해킹 보고서는 진단 전용 규칙 결과를 경고로 낮춤
        out = [dict(x, level="warning") if x["rule"] in ("R-24", "R-25", "R-26", "R-23") else x for x in out]
    if report == "diag":   # 진단 보고서는 시나리오를 싣지 않으므로 시나리오 쪽 문제는 경고로
        out = [dict(x, level="warning") if _is_scenario_where(x["where"]) else x for x in out]
    if report != "pentest":
        out = [x for x in out if x["rule"] != "R-28"]
    return out


def _is_scenario_where(where: str) -> bool:
    return bool(re.match(r"^(R[45] )?S\d+", where or ""))
