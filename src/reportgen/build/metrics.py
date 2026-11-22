"""집계 값(결과 3-2·4-2, 블루 1-2·1-3·8-2, 규격서 4-4 계산식)."""
from __future__ import annotations

from collections import Counter
from statistics import mean

from .. import refdata

SEVS = refdata.SEVERITY_ORDER


def result_counts(data: dict) -> dict:
    """대상별·구역별 위험도 건수(의도적 취약점 제외)."""
    assets = [a for a in data.get("assets", []) if a.get("scope") == "in_scope"]
    insts = [i for i in data.get("instances", []) if not i.get("intentional")]
    rows, zones = [], {}
    for a in assets:
        c = Counter(i["severity"] for i in insts if i["asset_id"] == a["asset_id"])
        row = {"zone": a["zone"], "asset_id": a["asset_id"], "name": a["name"], **{s: c.get(s, 0) for s in SEVS}}
        row["total"] = sum(c.get(s, 0) for s in SEVS)
        rows.append(row)
        z = zones.setdefault(a["zone"], {s: 0 for s in SEVS} | {"total": 0})
        for s in SEVS + ["total"]:
            z[s] += row[s]
    total = {s: sum(z[s] for z in zones.values()) for s in SEVS + ["total"]}
    by_sev = Counter(i["severity"] for i in insts)
    return {"rows": rows, "zones": zones, "total": total, "by_severity": dict(by_sev),
            "intentional": sum(1 for i in data.get("instances", []) if i.get("intentional")),
            "findings": len(data.get("findings", [])), "instances": len(insts)}


def _metrics(cases: list[dict], score_key: str, outcome_key: str) -> dict:
    thr = refdata.ptef().get("detection_threshold", 3)
    valid = [c for c in cases if c.get(outcome_key) and c.get(outcome_key) != "invalid"]
    scored = [c for c in valid if c.get(score_key) is not None]
    lat = [c["latency_sec"] for c in valid if c.get("latency_sec") is not None]
    oc = Counter(c.get(outcome_key) for c in valid)
    return {
        "cases": len(valid),
        "detection_rate": round(100 * sum(1 for c in scored if c[score_key] >= thr) / len(valid), 1) if valid else None,
        "avg_score": round(mean(c[score_key] for c in scored), 1) if scored else None,
        "blocked": oc.get("blocked", 0), "detected": oc.get("detected", 0), "not_detected": oc.get("not_detected", 0),
        "block_rate": round(100 * oc.get("blocked", 0) / len(valid), 1) if valid else None,
        "mttd_sec": round(mean(lat)) if lat else None,
        "score_dist": [sum(1 for c in scored if c[score_key] == k) for k in range(6)],
        "invalid": sum(1 for c in cases if c.get(outcome_key) == "invalid"),
    }


def blue_metrics(blue: dict) -> dict:
    tests = [t for t in blue.get("test_cases", []) if t.get("status") == "executed"]
    after_by_test = {}
    for fx in blue.get("detection_fixes", []):
        rt = fx.get("retest") or {}
        if rt.get("score_after") is not None or rt.get("outcome_after"):
            for tid in fx.get("test_ids", []):
                after_by_test[tid] = rt
    rows = []
    for t in tests:
        rt = after_by_test.get(t["test_id"], {})
        rows.append({**t, "score_after": rt.get("score_after", t.get("score")),
                     "outcome_after": rt.get("outcome_after") or t.get("outcome")})
    before = _metrics(rows, "score", "outcome")
    after = _metrics(rows, "score_after", "outcome_after")
    ack, res = [], []
    from ..dtutil import parse_dt as dt   # 시간대 없는 값은 KST로 봐서 +09:00 값과 뺄 수 있게

    for t in tests:
        first = min((dt(a.get("alert_at")) for a in t.get("alerts", []) if dt(a.get("alert_at"))), default=None)
        tr = t.get("triage") or {}
        if first and dt(tr.get("ack_at")):
            ack.append((dt(tr["ack_at"]) - first).total_seconds())
        if first and dt(tr.get("resolved_at")):
            res.append((dt(tr["resolved_at"]) - first).total_seconds())
    triaged = [t for t in tests if (t.get("triage") or {}).get("verdict")]
    fp = sum(1 for t in triaged if t["triage"]["verdict"] == "false_positive")
    gaps = Counter(t.get("gap") for t in tests if t.get("gap") and t.get("gap") != "none")
    gaps["invalid"] += sum(1 for t in tests if t.get("outcome") == "invalid")
    ops = blue.get("ops_stats") or {}
    return {
        "before": before, "after": after,
        "mtta_sec": round(mean(ack)) if ack else None, "mttr_sec": round(mean(res)) if res else None,
        "fp_rate": round(100 * fp / len(triaged), 1) if triaged else None,
        "gaps": dict(gaps), "planned": sum(1 for t in blue.get("test_cases", []) if t.get("status") == "planned"),
        "ops_fp_rate": round(100 * ops["false_positives"] / ops["alerts_total"], 1)
        if ops.get("alerts_total") and ops.get("false_positives") is not None else None,
        "rows": rows,
    }


def fmt_duration(sec: int | None) -> str:
    if sec is None:
        return "-"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}시간 {m}분 {s}초"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"
