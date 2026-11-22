"""AI 결과(results.jsonl)와 잠금(locked.yaml)을 canonical 데이터에 합쳐 보고서용 데이터(report.json)를 만듦."""
from __future__ import annotations

import copy
import json

from .ai.tasks import read_jsonl

PENDING = "[AI 작업 대기]"


def _set(data: dict, field: str, target: str, value) -> bool:
    blue = data.get("blue") or {}
    f = {x["finding_id"]: x for x in data.get("findings", [])}
    i = {x["instance_id"]: x for x in data.get("instances", [])}
    s = {x["step_id"]: x for sc in data.get("scenarios", []) for x in sc.get("steps", [])}
    e = {x["evidence_id"]: x for x in data.get("evidence", [])}
    t = {x["test_id"]: x for x in blue.get("test_cases", [])}
    fx = {x["fix_id"]: x for x in blue.get("detection_fixes", [])}
    if field == "finding.overview" and target in f:
        f[target]["overview"] = value
    elif field == "finding.exploit_scenario" and target in f:
        f[target]["exploit_scenario"] = value
    elif field == "finding.remediation.steps" and target in f:
        f[target]["remediation"]["steps"] = value if isinstance(value, list) else [x for x in str(value).split("\n") if x]
    elif field == "finding.remediation.verify" and target in f:
        f[target]["remediation"]["verify"] = value
    elif field == "finding_instance.poc.explanation" and target in i:
        i[target].setdefault("poc", {})["explanation"] = value
    elif field == "finding_instance.flow" and "#" in target:
        iid, k = target.rsplit("#", 1)
        flow = (i.get(iid) or {}).get("flow") or []
        if not k.isdigit() or int(k) >= len(flow) or "text" not in flow[int(k)]:
            return False
        flow[int(k)]["text"] = value if isinstance(value, str) else "\n".join(map(str, value))
    elif field == "finding_instance.diff" and target in i:
        i[target]["diff"] = value
    elif field == "scenario_step.flow" and "#" in target:
        sid, k = target.rsplit("#", 1)
        flow = (s.get(sid) or {}).get("flow") or []
        if not k.isdigit() or int(k) >= len(flow) or "text" not in flow[int(k)]:
            return False
        flow[int(k)]["text"] = value if isinstance(value, str) else "\n".join(map(str, value))
    elif field == "scenario_step.rationale" and target in s:
        s[target]["rationale"] = value
    elif field == "pentest.summary":
        data["pentest_summary"] = value
    elif field == "scenario_step.narrative" and target in s:
        s[target]["narrative"] = value
    elif field == "summary.overall":
        data["summary_overall"] = value
    elif field == "evidence.caption" and target in e:
        e[target]["caption"] = value
    elif field in ("blue.risk_summary", "blue.business_impact"):
        data.setdefault("blue", {})[field.split(".")[1]] = value
    elif field == "test_case.miss_analysis" and target in t:
        v = value if isinstance(value, list) else [value, "", ""]
        v = (v + ["", "", ""])[:3]
        t[target]["miss_analysis"] = {"expected_log": v[0], "collected": v[1], "needed_rule": v[2]}
    elif field.startswith("detection_fix.") and target in fx:
        fx[target][field.split(".")[1]] = value
    elif field == "incident.summary":
        data.setdefault("blue", {}).setdefault("incident", {})["summary"] = value
    elif field == "blue.lessons":
        items = value if isinstance(value, list) else [value]
        data.setdefault("blue", {})["lessons"] = [{"text": x.split(":", 1)[1].strip()} for x in items if x.startswith("교훈")]
        data["blue"]["strengths"] = [{"text": x.split(":", 1)[1].strip()} for x in items if x.startswith("잘 된 방어")]
    elif field == "project.summary_memo":
        data["project"]["summary_memo"] = value
    else:
        return False
    return True


def assemble(canonical: dict, tasks: list[dict], results: list[dict], locked: dict) -> tuple[dict, dict]:
    """(report_data, status) 반환. status[task_id] = locked | ai | pending."""
    data = copy.deepcopy(canonical)
    by_id = {}
    for r in results:
        if r.get("task_id") and not r.get("_error"):
            by_id[r["task_id"]] = r   # 같은 작업이 여러 번이면 마지막 결과
    status = {}
    for t in tasks:
        tid = t["task_id"]
        if tid in locked:
            _set(data, t["field"], t["target_id"], locked[tid])
            status[tid] = "locked"
        elif tid in by_id and by_id[tid].get("text") not in (None, "", []):
            _set(data, t["field"], t["target_id"], by_id[tid]["text"])
            status[tid] = "ai"
        else:
            # 그림 설명은 대기 중이어도 사람이 쓴 캡션·기본 설명을 그대로 둠
            if t["mode"] == "write" and t["field"] != "evidence.caption":
                _set(data, t["field"], t["target_id"], PENDING)
            status[tid] = "pending"
    return data, status


def save(path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_results(work) -> list[dict]:
    return read_jsonl(work / "results.jsonl")
