"""보고서 사이 연결(블루 → 레드 역참조)과 타임라인."""
from __future__ import annotations


def backrefs(data: dict) -> None:
    """블루팀 test_case.source_ref → 레드팀 단계 actual_detection, 건 test_ids."""
    tests = (data.get("blue") or {}).get("test_cases", [])
    steps = {s["step_id"]: s for sc in data.get("scenarios", []) for s in sc.get("steps", [])}
    insts = {i["instance_id"]: i for i in data.get("instances", [])}
    for t in tests:
        ref = t.get("source_ref")
        if t.get("source") == "scenario_step" and ref in steps:
            st = steps[ref]
            first_alert = min((a["alert_at"] for a in t.get("alerts", []) if a.get("alert_at")), default="")
            prev = st.get("actual_detection")
            # 같은 단계에 테스트가 여럿이면 가장 좋은 결과(차단 > 탐지 > 미탐)를 씀
            order = {"blocked": 0, "detected": 1, "not_detected": 2, "invalid": 3, None: 4}
            if not prev or order.get(t.get("outcome"), 4) < order.get(prev.get("outcome"), 4):
                st["actual_detection"] = {"outcome": t.get("outcome"), "alert_at": first_alert, "test_id": t["test_id"]}
            st.setdefault("test_ids", [])
            if t["test_id"] not in st["test_ids"]:
                st["test_ids"].append(t["test_id"])
        if t.get("source") == "finding_instance" and ref in insts:
            ids = insts[ref].setdefault("test_ids", [])
            if t["test_id"] not in ids:
                ids.append(t["test_id"])


def timeline(data: dict) -> list[dict]:
    """부록 E 전체 공격 타임라인(단계 시각 순)."""
    rows = []
    for sc in data.get("scenarios", []):
        for s in sc.get("steps", []):
            det = s.get("actual_detection") or {}
            rows.append({"at": s.get("start_at", ""), "end_at": s.get("end_at", ""), "source_ip": s.get("source_ip", ""),
                         "asset_id": s.get("asset_id", ""), "action": s.get("name", ""), "step_id": s["step_id"],
                         "defense": det.get("outcome") or "블루팀 검증 전"})
    return sorted(rows, key=lambda r: r["at"])
