"""canonical 데이터에 계산 값을 채움(규격서 출처 「계산」 필드). 사람이 쓴 값은 바꾸지 않음."""
from __future__ import annotations

from datetime import datetime

from .. import refdata
from ..intake.mapping import id_key
from . import link
from ..dtutil import parse_dt

def _dt(s: str) -> datetime | None:
    return parse_dt(s)   # 날짜만 있거나 시간대가 없는 값은 KST(dtutil)


def compute(data: dict) -> dict:
    findings = data.get("findings", [])
    insts = data.get("instances", [])
    by_f: dict[str, list[dict]] = {}
    for i in insts:
        by_f.setdefault(i["finding_id"], []).append(i)
    assets = {a["asset_id"]: a for a in data.get("assets", [])}

    # 취약점: 위험도(대표 건 등급, 없으면 최고), 건수, 대상
    for f in findings:
        its = sorted(by_f.get(f["finding_id"], []), key=lambda i: id_key(i["instance_id"]))
        rep = next((i for i in its if i["instance_id"].endswith("-1")), its[0] if its else None)
        best = min((i.get("severity") for i in its), key=refdata.sev_rank, default=None)
        f["severity"] = (rep or {}).get("severity") or best
        f["max_severity"] = best
        f["instance_ids"] = [i["instance_id"] for i in its]
        f["count"] = len(its)
        f["count_intentional"] = sum(1 for i in its if i.get("intentional"))
        f["asset_ids"] = sorted({i["asset_id"] for i in its})
        f["max_score"] = max((i["cvss"].get("score") or 0 for i in its), default=None)
        f["rep_score"] = (rep or {}).get("cvss", {}).get("score")
        f["step_ids"] = sorted({s for i in its for s in i.get("step_ids", [])}, key=id_key)
        f["owasp_label"] = refdata.owasp_label(f.get("owasp_2025"))
        f["representative_id"] = rep["instance_id"] if rep else None

    # 건: 구역, 위험도 라벨
    for i in insts:
        a = assets.get(i["asset_id"], {})
        i["zone"] = a.get("zone")

    # 진단 항목: 범주명·판단 기준·점검 취약점(reference 고정 문구)
    for c in data.get("check_items", []):
        ref = refdata.owasp().get(c.get("code"), {})
        c.setdefault("name", ref.get("name", ""))
        if not c.get("name"):
            c["name"] = ref.get("name", "")
        c["criteria"] = c.get("criteria") or ref.get("criteria", {})
        items = c.get("checked_items")
        if not items:   # 노션에 「점검 취약점」을 적지 않았으면 reference 전체를 씀(검토 목록에 표시)
            c["checked_items"] = [dict(x) for x in ref.get("items", [])]
            c["checked_items_default"] = True
        else:
            filled = []
            for it in items:
                r = refdata.owasp_item(c["code"], it["title"]) or {}
                filled.append({"title": it["title"], "cwe": it.get("cwe") or r.get("cwe", []),
                               "check_points": it.get("check_points") or r.get("check_points", [])})
            c["checked_items"] = filled
        f_codes = {f["finding_id"]: f.get("owasp_2025") for f in findings}
        for r in c.get("results", []):
            r["instance_ids"] = [i["instance_id"] for i in insts
                                 if f_codes.get(i["finding_id"]) == c.get("code") and i["asset_id"] == r["asset_id"]]

    # 시나리오: 블루 역참조, 목표 걸린 시간·사용 취약점
    link.backrefs(data)
    steps_by_sc = {sc["scenario_id"]: sc.get("steps", []) for sc in data.get("scenarios", [])}
    for sc in data.get("scenarios", []):
        names = [s.get("name", "") for s in sc.get("steps", [])]
        sc.setdefault("path_summary", " → ".join(names))
        if not sc.get("path_summary"):
            sc["path_summary"] = " → ".join(names)
        if not sc.get("result_summary"):
            failed = [s for s in sc.get("steps", []) if (s.get("result") or {}).get("status") == "failed"]
            sc["result_summary_auto"] = (f"{failed[0]['step_id']}에서 막힘" if failed else "")
    for o in data.get("objectives", []):
        steps = [s for sid in o.get("scenario_ids", []) for s in steps_by_sc.get(sid, [])]
        o["instance_ids"] = sorted({i for s in steps for i in s.get("instance_ids", [])}, key=id_key)
        starts = [_dt(s.get("start_at")) for s in steps if _dt(s.get("start_at"))]
        ends = [_dt(s.get("end_at")) for s in steps
                if _dt(s.get("end_at")) and (s.get("result") or {}).get("status") == "success"]
        if starts and ends and o.get("status") in ("achieved", "partial"):
            o["time_to_achieve_sec"] = int((max(ends) - min(starts)).total_seconds())

    # 블루: 탐지 소요(첫 경보 − 실행)
    for t in (data.get("blue") or {}).get("test_cases", []):
        ex = _dt(t.get("executed_at"))
        firsts = [_dt(a.get("alert_at")) for a in t.get("alerts", []) if _dt(a.get("alert_at"))]
        if ex and firsts:
            t["latency_sec"] = int((min(firsts) - ex).total_seconds())

    # 증거: 페이지별 목록
    ev_by_owner: dict[str, list[str]] = {}
    for e in data.get("evidence", []):
        ev_by_owner.setdefault(e["owner_id"].split(":")[0], []).append(e["evidence_id"])
    for i in insts:
        i["evidence_ids"] = ev_by_owner.get(i["instance_id"], [])
    for sc in data.get("scenarios", []):
        for s in sc.get("steps", []):
            s["evidence_ids"] = ev_by_owner.get(s["step_id"], [])
    for t in (data.get("blue") or {}).get("test_cases", []):
        t["evidence_ids"] = ev_by_owner.get(t["test_id"], [])
    for fx in (data.get("blue") or {}).get("detection_fixes", []):
        fx.setdefault("retest", {})["evidence_ids"] = ev_by_owner.get(fx["fix_id"], [])

    data["timeline"] = link.timeline(data)
    return data
