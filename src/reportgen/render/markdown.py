"""보고서 데이터 → Markdown(templates/*.md.j2). Markdown은 검토용으로도 남기고, docx.py가 DOCX로 바꿈."""
from __future__ import annotations

import os
import re as _re_mod
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined

from .. import refdata
from ..build import assets as assets_mod
from ..build import metrics
from ..config import TOOL_ROOT
from ..intake.mapping import id_key


def _cell(v) -> str:
    """표 칸에 넣을 값: 줄바꿈·파이프 정리."""
    if v is None or v == "" or isinstance(v, Undefined):
        return "-"
    if isinstance(v, (list, tuple)):
        v = ", ".join(str(x) for x in v if x not in (None, "")) or "-"
    # 칸 안의 「|」는 지우지 않고 이스케이프(정규식 등 원문 유지)
    return str(v).replace("\\|", "|").replace("|", "\\|").replace("\n", " ")


_ID_NUM = __import__("re").compile(r"^(.*?)(\d+)$")


def _idrange(v) -> str:
    """연속 번호를 물결로 묶음: [E-067, E-068, E-069, E-072] → 「E-067~069, E-072」. 피드백: 번호 나열 대신 범위."""
    if v is None or isinstance(v, Undefined) or v == "" or v == []:
        return "-"
    if isinstance(v, str):
        return _cell(v)
    ids = [str(x) for x in v if x not in (None, "")]
    out, run = [], []

    def close():
        if not run:
            return
        if len(run) >= 3:
            pre, first = _ID_NUM.match(run[0]).groups()
            last = _ID_NUM.match(run[-1]).group(2)
            out.append(f"{pre}{first}~{last}")
        else:
            out.extend(run)
        run.clear()

    for x in ids:
        m = _ID_NUM.match(x)
        if run and m:
            pm = _ID_NUM.match(run[-1])
            if pm.group(1) == m.group(1) and int(m.group(2)) == int(pm.group(2)) + 1:
                run.append(x)
                continue
        close()
        if m:
            run.append(x)
        else:
            out.append(x)
    close()
    return ", ".join(out) or "-"


def _hosts(values) -> str:
    """대상 칸: 같은 호스트를 한 번만(피드백: 같은 호스트 3번 반복). 괄호 속 서버 이름도 같은 것으로 봄."""
    import re as _re
    seen, out = set(), []
    for v in values or []:
        if not v:
            continue
        v = str(v).strip()
        main = _re.sub(r"^https?://", "", _re.sub(r"\s*\(.*\)\s*$", "", v)).rstrip("/").lower()
        inner = {x.strip().lower() for x in _re.findall(r"\(([^)]*)\)", v)}
        if main in seen:
            continue
        seen |= {main} | inner
        out.append(v)
    return ", ".join(out) or "-"


def _paras(text) -> str:
    """흐름의 글 조각 → Markdown 문단. 일반 줄은 문단마다 빈 줄, 목록 줄은 붙여 둠."""
    lines = [x.rstrip() for x in str(text or "").splitlines() if x.strip()]
    out = []
    for n, line in enumerate(lines):
        is_item = line.lstrip().startswith(("- ", "* ")) or bool(__import__("re").match(r"\d+\. ", line.lstrip()))
        prev_item = n and (lines[n - 1].lstrip().startswith(("- ", "* ")) or
                           bool(__import__("re").match(r"\d+\. ", lines[n - 1].lstrip())))
        if n and not (is_item and prev_item):
            out.append("")
        out.append(line)
    return "\n".join(out)


def _pick_accounts(accts, limit: int = 5) -> list:
    """본문에 보일 테스트 계정 limit개(2026-11-22).
    권한마다 표에서 처음 나오는 계정을 먼저 고르고, 남는 자리는 표 순서대로 채움. 돌려줄 때는 표 순서를 유지함."""
    accts = list(accts or [])
    picked: list[int] = []
    seen: set[str] = set()
    for i, t in enumerate(accts):
        role = str((t.get("role") if isinstance(t, dict) else getattr(t, "role", "")) or "").strip()
        if role not in seen:
            seen.add(role)
            picked.append(i)
    picked = picked[:limit]
    for i in range(len(accts)):
        if len(picked) >= limit:
            break
        if i not in picked:
            picked.append(i)
    return [accts[i] for i in sorted(picked)]


def _ko(v) -> str:
    """「초기 침투 (Initial Access)」 → 「초기 침투」(괄호 속 영문 병기를 뺌). 한글이 없으면 그대로."""
    t = str(v or "").strip()
    k = _re_mod.sub(r"\s*\([A-Za-z0-9 &/,.\-]+\)", "", t).strip()
    return _cell(k if _re_mod.search(r"[가-힣]", k) else t) if t else "-"


def _sev(v) -> str:
    return refdata.SEVERITY_LABEL.get(v, v or "-")


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TOOL_ROOT / "templates")), undefined=Undefined,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    env.filters.update({
        "cell": _cell, "sev": _sev, "idrange": _idrange, "hosts": _hosts, "paras": _paras,
        "zone": lambda v: refdata.ZONE_LABEL.get(v, v or "-"),
        "agentno": lambda v: assets_mod.parse_agent(v)[0] or _cell(v),
        "check": lambda v: refdata.CHECK_LABEL.get(v, v or "-"),
        "status": lambda v: refdata.STATUS_LABEL.get(v, v or "-"),
        "prio": lambda v: refdata.FIX_PRIORITY_LABEL.get(v, v or "-"),
        "objtype": lambda v: refdata.OBJ_TYPE_LABEL.get(v, v or "-"),
        "objstatus": lambda v: refdata.OBJ_STATUS_LABEL.get(v, v or "-"),
        "startcond": lambda v: refdata.START_COND_LABEL.get(v, v or "-"),
        "outcome": lambda v: refdata.OUTCOME_LABEL.get(v, v or "-"),
        "gap": lambda v: refdata.GAP_LABEL.get(v, v or "-"),
        "patchtype": lambda v: refdata.PATCH_TYPE_LABEL.get(v, v or "-"),
        "source": lambda v: refdata.SOURCE_LABEL.get(v, v or "-"),
        "owasp": refdata.owasp_label,
        "dur": lambda v: metrics.fmt_duration(v if isinstance(v, (int, float)) else None),
        "pct": lambda v: f"{v}%" if isinstance(v, (int, float)) else "-",
        "num": lambda v: v if isinstance(v, (int, float, str)) and v != "" else "-",
        "ko": _ko,
        "pick_accounts": _pick_accounts,
        # 계정 이름: 노션이 붙인 메일 링크 「[a***@x.com](mailto:…)」를 글자만 남김
        "acct": lambda v: _re_mod.sub(r"\[([^\]]*)\]\(mailto:[^)]*\)", r"\1", str(v or "")).strip() or "-",
        "hms": lambda v: (_re_mod.search(r"T?(\d{2}:\d{2}(:\d{2})?)", str(v or "")) or [None, "-"])[1] if v else "-",
        "day": lambda v: str(v or "")[:10],
        "kst": lambda v: (v if isinstance(v, str) and v else "-").replace("T", " ").replace("+09:00", " KST"),
        "yn": lambda v: "예" if v else "아니오",
        "onoff": lambda v: "켬" if v else "끔",
        "indent": lambda s, n=2: ("\n" + " " * n).join(str(s).splitlines()),
        "evkind": lambda v: {"screenshot": "스크린샷", "http": "요청·응답", "log": "로그",
                             "alert_json": "경보 JSON"}.get(v, v or "-"),
        "decoder": lambda v: {"builtin": "기본", "custom": "커스텀", "none": "없음"}.get(v, v or "-"),
        "module": lambda v: {"fim": "파일 무결성 감시(FIM)", "sca": "보안 설정 평가(SCA)",
                             "vulnerability_detection": "취약점 탐지", "active_response": "Active Response"}.get(v, v or "-"),
        "cloud": lambda v: {"security_group": "보안그룹 변경", "iam": "IAM 변경",
                            "console_login": "콘솔 로그인"}.get(v, v or "-"),
        "taskstatus": lambda v: {"todo": "미착수", "in_progress": "진행", "done": "완료"}.get(v, v or "-"),
        "pick": lambda ids, table: [table[x] for x in (ids or []) if x in table],
        "scen": lambda ids: list(dict.fromkeys(str(x).split("-")[0] for x in (ids or []))),
    })
    from .pentest_ctx import FILTERS as _PT_FILTERS   # 모의해킹 보고서(2026-11-18)
    env.filters.update(_PT_FILTERS)
    env.tests.update({"search": lambda v, pat: bool(v) and str(pat) in str(v)})
    return env


def _evidence_index(data: dict, out_dir: Path) -> dict:
    ev = {}
    for n, e in enumerate(sorted(data.get("evidence", []), key=lambda x: x["evidence_id"]), 1):
        e = dict(e)
        if e.get("path"):
            try:
                e["relpath"] = os.path.relpath(e["path"], out_dir)
            except ValueError:
                e["relpath"] = e["path"]
        e["figure_no"] = n
        if e["kind"] != "screenshot" and e.get("path", "").endswith(".txt"):
            try:
                e["content"] = Path(e["path"]).read_text(encoding="utf-8")
            except OSError:
                e["content"] = ""
        ev[e["evidence_id"]] = e
    return ev


def diag_context(data: dict, out_dir: Path) -> dict:
    assets = [a for a in data.get("assets", []) if a.get("scope") == "in_scope"]
    out_scope = [a for a in data.get("assets", []) if a.get("scope") == "out_of_scope"]
    findings = data.get("findings", [])
    insts = data.get("instances", [])
    by_f = {f["finding_id"]: [i for i in insts if i["finding_id"] == f["finding_id"]] for f in findings}
    for f in findings:
        by_f[f["finding_id"]].sort(key=lambda i: id_key(i["instance_id"]))
    sorted_findings = sorted(findings, key=lambda f: (refdata.sev_rank(f.get("severity")), -(f.get("rep_score") or 0),
                                                      -len(f.get("step_ids") or []), id_key(f["finding_id"])))
    # 5장: 구역 → 대상 → 취약점(대표 건 자산 기준, 위험도 순)
    sections = []
    zones = ["external_dmz", "internal_admin"]
    for z in zones:
        for a in [x for x in assets if x["zone"] == z]:
            fs = [f for f in sorted_findings if by_f[f["finding_id"]] and
                  next((i for i in by_f[f["finding_id"]] if i["instance_id"] == f.get("representative_id")),
                       by_f[f["finding_id"]][0])["asset_id"] == a["asset_id"]]
            sections.append({"zone": z, "asset": a, "findings": fs})
    steps = {s["step_id"]: s for sc in data.get("scenarios", []) for s in sc.get("steps", [])}
    failed_steps = [s for s in steps.values() if (s.get("result") or {}).get("status") == "failed"]
    root_causes = {}
    for f in findings:
        if f.get("root_cause"):
            root_causes.setdefault(f["root_cause"], []).append(f["finding_id"])
    retests = data.get("retests", [])
    fixed = sum(1 for r in retests if r.get("result") == "fixed")
    patches = {p["patch_id"]: p for p in data.get("patches", [])}
    tools = (data.get("project") or {}).get("tools") or []
    ev = _evidence_index(data, out_dir)
    return {
        "p": data.get("project") or {}, "assets": assets, "out_scope": out_scope,
        "objectives": data.get("objectives", []), "check_items": data.get("check_items", []),
        "findings": sorted_findings, "by_f": by_f, "insts": {i["instance_id"]: i for i in insts},
        "sections": sections, "scenarios": data.get("scenarios", []), "steps": steps, "failed_steps": failed_steps,
        "counts": metrics.result_counts(data), "root_causes": root_causes, "retests": retests, "patches": patches,
        "retest_rate": (fixed, len(retests)), "ev": ev, "summary_overall": data.get("summary_overall", ""),
        "timeline": data.get("timeline", []), "tools": tools, "sev_order": refdata.SEVERITY_ORDER,
        "zones": zones, "owasp_ref": refdata.owasp(),
        "asset_ids": [a["asset_id"] for a in assets if a["asset_id"] != "A-04"] or [a["asset_id"] for a in assets],
        "iocs": _iocs(data),
        "charts": diag_charts(metrics.result_counts(data), assets),
    }


def _iocs(data: dict) -> list[dict]:
    rows = []
    for s in data.get("timeline", []):
        if s.get("source_ip"):
            rows.append({"type": "IP", "value": s["source_ip"], "ref": s["step_id"]})
    seen, out = set(), []
    for r in rows:
        if (r["type"], r["value"]) not in seen:
            seen.add((r["type"], r["value"]))
            out.append(r)
    return out


from .theme import CHART_AFTER as AFTER, CHART_BEFORE as BEFORE, OUTCOME as _OC  # noqa: E402


def metric_charts(m: dict) -> dict:
    """1-2 핵심 지표 차트(피드백: 표 대신 그래프). render/chart.py가 읽는 JSON 문자열."""
    import json
    bf, af = m.get("before") or {}, m.get("after") or {}
    cats = ["개선 전", "개선 후"]

    def pair(title, key, mx=None, fmt="General", major=None):
        spec = {"title": title, "categories": cats, "legend": False, "max": mx, "format": fmt, "gap": 70,
                "series": [{"name": title, "values": [bf.get(key), af.get(key)], "colors": [BEFORE, AFTER]}]}
        if major:
            spec["major"] = major
        return spec

    outcome = {"title": "탐지 결과 (건)", "categories": cats, "grouping": "stacked", "gap": 70,
               "series": [{"name": "차단", "values": [bf.get("blocked"), af.get("blocked")], "color": _OC["차단"]},
                          {"name": "탐지", "values": [bf.get("detected"), af.get("detected")], "color": _OC["탐지"]},
                          {"name": "미탐", "values": [bf.get("not_detected"), af.get("not_detected")], "color": _OC["미탐"]}]}
    row = {"row": [pair("탐지율 (%)", "detection_rate", 100, '0.0"%"', 25),
                   pair("평균 점수 (0~5점)", "avg_score", 5, "0.0", 1), outcome]}
    dist = {"title": "점수별 케이스 수 (PTEF 0~5점)", "categories": [f"{k}점" for k in range(6)], "gap": 50,
            "height_cm": 5.5, "format": "0;-0;;",
            "series": [{"name": "개선 전", "values": bf.get("score_dist") or [0] * 6, "color": BEFORE},
                       {"name": "개선 후", "values": af.get("score_dist") or [0] * 6, "color": AFTER}]}
    top = max([*(bf.get("score_dist") or [0]), *(af.get("score_dist") or [0])])
    if top <= 8:   # 건수가 적으면 눈금을 1건 단위로(0.5 눈금 방지)
        dist["major"] = 1
    if (bf.get("cases") or 0) <= 8:
        outcome["major"] = 1
    return {"row": json.dumps(row, ensure_ascii=False), "dist": json.dumps(dist, ensure_ascii=False)}


def diag_charts(counts: dict, assets: list[dict]) -> dict:
    """4-1 요약 차트: 위험도별 건수(등급 색), 대상별 위험도 분포(가로 누적 막대). render/chart.py가 읽는 JSON."""
    import json
    from .theme import SEVERITY as _SC
    sevs = refdata.SEVERITY_ORDER
    labels = [refdata.SEVERITY_LABEL[s] for s in sevs]
    total = counts.get("total") or {}
    by_sev = {"title": "위험도별 건수", "categories": labels, "legend": False, "gap": 60, "format": "0;-0;;",
              "series": [{"name": "건수", "values": [total.get(s, 0) for s in sevs],
                          "colors": [_SC[s] for s in sevs]}]}
    names = {a["asset_id"]: a.get("name") or "" for a in assets}
    rows = [r for r in counts.get("rows", []) if r.get("total")]
    by_asset = {"title": "대상별 위험도 분포 (건)", "categories": [f"{r['asset_id']} {names.get(r['asset_id'], '')}".strip()
                                                         for r in rows],
                "grouping": "stacked", "dir": "bar", "gap": 60,
                "series": [{"name": refdata.SEVERITY_LABEL[s], "values": [r.get(s, 0) for r in rows], "color": _SC[s]}
                           for s in sevs if any(r.get(s) for r in rows)]}
    top = max([total.get(s, 0) for s in sevs] or [0])
    if top <= 8:
        by_sev["major"] = 1
    return {"row": json.dumps({"row": [by_sev, by_asset]}, ensure_ascii=False)}


def blue_context(data: dict, out_dir: Path) -> dict:
    blue = data.get("blue") or {}
    m = metrics.blue_metrics(blue)
    amap = assets_mod.asset_map(data)
    tests = blue.get("test_cases", [])
    by_source = {}
    for t in tests:
        by_source[t.get("source")] = by_source.get(t.get("source"), 0) + 1
    misses = [t for t in tests if t.get("status") == "executed" and t.get("outcome") != "invalid"
              and (t.get("outcome") == "not_detected" or (t.get("score") is not None and t["score"] < 3))]
    tests_by_id = {t["test_id"]: t for t in tests}
    retest_rows = []
    for fx in blue.get("detection_fixes", []):
        rt = fx.get("retest") or {}
        if rt.get("score_after") is None and not rt.get("outcome_after"):
            continue
        for tid in fx.get("test_ids", []):
            t = tests_by_id.get(tid, {})
            retest_rows.append({"test_id": tid, "fix_id": fx["fix_id"], "name": fx.get("name"),
                                "score_before": t.get("score"), "score_after": rt.get("score_after"),
                                "outcome_before": t.get("outcome"), "outcome_after": rt.get("outcome_after"),
                                "at": rt.get("at"), "evidence_ids": rt.get("evidence_ids", [])})
    fix_of = {}   # 5-2 끊김 표 「조치」 칸: 케이스 → [(F-ID, 재검증 점수)]
    for fx in blue.get("detection_fixes", []):
        for tid in fx.get("test_ids", []):
            fix_of.setdefault(tid, []).append({"fix_id": fx["fix_id"],
                                               "score_after": (fx.get("retest") or {}).get("score_after")})
    return {"p": data.get("project") or {}, "b": blue, "m": m, "tests": tests, "by_source": by_source,
            "fix_of": fix_of,
            "misses": misses, "ev": _evidence_index(data, out_dir), "assets": data.get("assets", []),
            "zone_of": {a["asset_id"]: a.get("zone") for a in data.get("assets", [])},
            "retest_rows": retest_rows, "ptef": refdata.ptef(), "gaps_ref": refdata.ptef().get("gaps", []),
            "rules_no_src": _rules_no_src(blue), "rules_xml_cat": _rules_xml_cat(blue), "charts": metric_charts(m),
            "amap": amap, "alabel": lambda ids: ", ".join(amap[i]["label"] if i in amap else i
                                                          for i in assets_mod.split_ids(ids)) or "-"}


def _rules_xml_cat(blue: dict) -> list[int]:
    """B5 「룰 전문」에는 없고 팀 페이지에만 XML이 있는 참조 룰(부록 A에 실음)."""
    from ..validate.output import RULE_ID_IN_XML, rule_refs
    refs, _ = rule_refs(blue)
    b5 = {int(x) for fx in blue.get("detection_fixes", []) for x in RULE_ID_IN_XML.findall(fx.get("rule_source") or "")}
    return [r for r in refs if r not in b5]


_NO_RECORD = "팀 기록 없음"
_MARK = __import__("re").compile(r"\[(?:범위 )?확인 필요(?::[^\]]*)?\]")


def no_record(md: str) -> str:
    """블루 보고서(2026-11-21 Kim): 블루 담당이 없어 팀 와주 페이지에 없는 값은 더 채울 수 없음.
    남은 「[확인 필요]」를 「팀 기록 없음」으로 바꿈. 칸·「항목 ::」 값 자리는 그대로, 문장 뒤에 붙은 것은 괄호로,
    제목 줄에서는 지움."""
    import re
    out = []
    for line in md.split("\n"):
        if line.lstrip().startswith("#"):
            line = re.sub(r"\s*" + _MARK.pattern, "", line)
        else:
            def rep(m):
                before = line[:m.start()].rstrip()
                if not before or before.endswith(("::", "|", ":", "-")) or before.endswith("—"):
                    return _NO_RECORD
                return f"({_NO_RECORD})"
            line = _MARK.sub(rep, line)
            line = line.replace(f"{_NO_RECORD} {_NO_RECORD}", _NO_RECORD)
        out.append(line)
    return "\n".join(out)


def _rules_no_src(blue: dict) -> list[int]:
    from ..validate.output import rule_refs
    refs, have = rule_refs(blue)
    return [r for r in refs if r not in have]


def plan_context(data: dict, out_dir: Path) -> dict:
    p = data.get("project") or {}
    return {"p": p, "assets": data.get("assets", []), "objectives": data.get("objectives", []),
            "tools": p.get("tools") or [], "ev": _evidence_index(data, out_dir)}


def render(report: str, data: dict, out_dir: Path) -> str:
    env = _env()
    if report == "pentest":   # 2026-11-18 진단·모의해킹 분리: 모의해킹은 진단 컨텍스트에 시나리오 값을 더함
        from .pentest_ctx import pentest_context
        ctx = pentest_context(data, out_dir, diag_context(data, out_dir))
    else:
        ctx = {"diag": diag_context, "blue": blue_context,
               "plan": plan_context}[report](data, out_dir)
    md = env.get_template(f"{report}.md.j2").render(**ctx)
    if report == "blue" and (data.get("project") or {}).get("blue_no_record", True):
        md = no_record(md)
    return md
