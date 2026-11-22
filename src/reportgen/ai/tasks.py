"""AI 할 일 만들기(규격서 5-3, 5-8 ③).

- 다듬기(polish): 사람이 쓴 원문이 있을 때만 만듦. 원문이 비면 AI가 채우지 않고 review.md ②(사람이 채울 사실)로 보냄
- 작성(write): 입력 데이터로 새 문장을 씀(확인 방법, 단계 수행 내용, 총평, 캡션, 블루 요약 등)
- 마스킹 완료가 거짓인 페이지의 값은 넣지 않음(모델 전송 금지, 규격서 5-1)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import refdata
from ..build import metrics
from .prompt_builder import build_prompt

POLISH_FIELDS = {
    "finding.overview": ("개요", "ST-02", "어디에서 어떤 이유로 발생하는지 한두 줄. 결과 문장이 아니라 원인 설명이므로 「~함·~됨」으로 끝냄"),
    "finding.exploit_scenario": ("악용 시나리오", "ST-02a", "확인한 것과 가능성을 나눈 구분을 유지함"),
    "finding_instance.poc.explanation": ("공격 설명", "ST-02a", "페이로드의 각 부분이 하는 일을 빼지 않음. 요약 금지"),
    "finding_instance.diff": ("대표 건과 다른 점", "ST-02a", "위치·파라미터와 다른 부분만 씀"),
    "finding_instance.flow": ("상세 설명(그림 사이 문단)", "ST-02a",
                              "그림 앞뒤에 놓이는 한 문단임. 줄 수와 목록 표시(「- 」, 「1. 」)를 유지하고 "
                              "다른 문단의 내용을 끌어오지 않음. 그림 번호는 쓰지 않음"),
    "finding.remediation.steps": ("조치방안", "ST-02", "text는 문자열 배열. 항목 수와 순서를 유지함"),
    "scenario_step.flow": ("단계 수행 내용(그림 사이 문단)", "ST-02a",
                           "그림 앞뒤에 놓이는 한 문단임. 줄 수와 목록 표시를 유지하고 명령·경로·IP는 바꾸지 않음. "
                           "비밀값이 보이면 값 대신 「[가림]」으로 씀"),
    "scenario_step.rationale": ("판단 근거", "ST-02a", "왜 이 방법을 썼는지. 원문에 없는 이유를 더하지 않음"),
}

FIELD_LEN_KEY = {
    "finding.remediation.steps": "finding.remediation.steps",
    "finding.remediation.verify": "finding.remediation.verify",
    "scenario_step.narrative": "scenario_step.narrative",
    "summary.overall": "summary.overall",
    "pentest.summary": "pentest.summary",
    "evidence.caption": "evidence.caption",
    "blue.risk_summary": "blue.risk_summary",
    "blue.business_impact": "blue.business_impact",
    "incident.summary": "incident.summary",
}


def _len(field: str) -> dict:
    return refdata.style().get("field_length", {}).get(FIELD_LEN_KEY.get(field, field), {})


def _len_text(spec: dict) -> str:
    if "sentences" in spec:
        a, b = spec["sentences"]
        return f"{a}~{b}문장" + (f", {spec['max_chars']}자 이내" if spec.get("max_chars") else "")
    if "ratio_to_source" in spec:
        a, b = spec["ratio_to_source"]
        return f"원문 길이의 {int(a * 100)}~{int(b * 100)}%"
    if "items" in spec:
        a, b = spec["items"]
        return f"{a}~{b}개 항목"
    return "제한 없음"


def _task(mode: str, field: str, target_id: str, template: str, *, source=None, context=None,
          allowed_ids=None, style="ST-02", label="", note="") -> dict:
    spec = _len(field)
    prompt = build_prompt(template, field_label=label or field, style=style, length=_len_text(spec),
                          field_note=note, context=context or {}, source=source)
    return {"task_id": f"{target_id}:{field}", "mode": mode, "field": field, "target_id": target_id,
            "prompt": prompt, "source_text": source if isinstance(source, str) else (
                json.dumps(source, ensure_ascii=False) if source is not None else None),
            "context": context or {}, "allowed_ids": sorted(set(allowed_ids or [])), "length": spec, "style": style}


def make_tasks(data: dict, report: str) -> tuple[list[dict], list[dict]]:
    """(tasks, human_todo) 반환. human_todo = review.md ② 사람이 채울 칸."""
    tasks, todo = [], []
    if report == "diag":
        _diag_tasks(data, tasks, todo)
    elif report == "pentest":
        _pentest_tasks(data, tasks, todo)
    elif report == "blue":
        _blue_tasks(data, tasks, todo)
    elif report == "plan":
        memo = (data.get("project") or {}).get("summary_memo")
        if memo:
            tasks.append(_task("polish", "project.summary_memo", "P1", "polish.md", source=memo, label="요약",
                               style="ST-02", note="수행 계획서 0-1 요약. 3~4문장"))
    return tasks, todo


def _diag_tasks(data: dict, tasks: list, todo: list, scenarios: bool = False) -> None:
    """진단 보고서. scenarios=True는 옛 한 권짜리 결과 보고서(2026-11-22 없앰)용으로, 지금은 부르는 곳이 없음."""
    insts = {i["instance_id"]: i for i in data.get("instances", [])}
    for f in data.get("findings", []):
        fid = f["finding_id"]
        its = [insts[x] for x in f.get("instance_ids", []) if x in insts]
        if not all(i.get("masked") for i in its) or not f.get("masked", True):
            todo.append({"where": fid, "what": "마스킹 완료가 꺼진 건이 있어 AI 작업을 만들지 않음"})
            continue
        ctx = {"finding_id": fid, "title": f["title"], "owasp": f.get("owasp_label"), "cwe": f.get("cwe"),
               "severity": refdata.SEVERITY_LABEL.get(f.get("severity"), ""),
               "locations": [f"{i['instance_id']} {i['location'].get('method', '')} {i['location'].get('url', '')}".strip()
                             for i in its]}
        allowed = [fid] + [i["instance_id"] for i in its]
        for field in ("finding.overview", "finding.exploit_scenario"):
            src = f.get(field.split(".")[1])
            label, style, note = POLISH_FIELDS[field]
            if src:
                tasks.append(_task("polish", field, fid, "polish.md", source=src, context=ctx, allowed_ids=allowed,
                                   style=style, label=label, note=note))
            else:
                todo.append({"where": fid, "what": f"R2 본문 「{label}」이 비어 있음(사람이 써야 함)"})
        steps = (f.get("remediation") or {}).get("steps") or []
        if steps:
            label, style, note = POLISH_FIELDS["finding.remediation.steps"]
            tasks.append(_task("polish", "finding.remediation.steps", fid, "polish.md", source=steps, context=ctx,
                               allowed_ids=allowed, style=style, label=label, note=note))
        else:
            todo.append({"where": fid, "what": "R2 본문 「조치방안」이 비어 있음(사람이 써야 함)"})
        rep = insts.get(f.get("representative_id") or "")
        if rep and rep.get("poc"):
            poc = rep["poc"]
            vctx = dict(ctx, representative=rep["instance_id"], steps=poc.get("steps", []),
                        request=poc.get("request", ""))
            tasks.append(_task("write", "finding.remediation.verify", fid, "remediation_verify.md", context=vctx,
                               allowed_ids=allowed, style="ST-02"))
        for i in its:
            flow_texts = [(k, seg["text"]) for k, seg in enumerate(i.get("flow") or []) if seg.get("text")]
            if flow_texts:
                # 글·그림을 번갈아 싣는 경우: 그림 사이 문단을 하나씩 다듬음(그림 자리는 그대로)
                label, style, note = POLISH_FIELDS["finding_instance.flow"]
                for k, txt in flow_texts:
                    tasks.append(_task("polish", "finding_instance.flow", f"{i['instance_id']}#{k}", "polish.md",
                                       source=txt, context={"location": i["location"]}, allowed_ids=allowed,
                                       style=style, label=label, note=note))
                continue
            if i["instance_id"].endswith("-1"):
                exp = (i.get("poc") or {}).get("explanation")
                if exp:
                    label, style, note = POLISH_FIELDS["finding_instance.poc.explanation"]
                    tasks.append(_task("polish", "finding_instance.poc.explanation", i["instance_id"], "polish.md",
                                       source=exp, context={"request": (i.get("poc") or {}).get("request", "")},
                                       allowed_ids=allowed, style=style, label=label, note=note))
            elif i.get("diff"):
                label, style, note = POLISH_FIELDS["finding_instance.diff"]
                tasks.append(_task("polish", "finding_instance.diff", i["instance_id"], "polish.md", source=i["diff"],
                                   context={"location": i["location"]}, allowed_ids=allowed, style=style,
                                   label=label, note=note))
    for sc in (data.get("scenarios", []) if scenarios else []):
        for s in sc.get("steps", []):
            if not s.get("masked"):
                todo.append({"where": s["step_id"], "what": "마스킹 완료가 꺼져 있어 수행 내용 정리를 만들지 않음"})
                continue
            if s.get("actions"):
                ctx = {"step_id": s["step_id"], "name": s.get("name"), "purpose": s.get("purpose"),
                       "instance_ids": s.get("instance_ids", []), "actions": s["actions"],
                       "result": s.get("result")}
                tasks.append(_task("write", "scenario_step.narrative", s["step_id"], "step_narrative.md", context=ctx,
                                   allowed_ids=[s["step_id"]] + s.get("instance_ids", []), style="ST-02a"))
    # 4-1 총평
    cnt = metrics.result_counts(data)
    top = sorted(data.get("findings", []), key=lambda f: (refdata.sev_rank(f.get("severity")), -(f.get("rep_score") or 0)))
    ctx = {"counts_by_severity": {refdata.SEVERITY_LABEL[k]: v for k, v in cnt["by_severity"].items()},
           "total_instances": cnt["instances"], "total_findings": cnt["findings"],
           "by_asset": [{"asset": r["name"], "total": r["total"]} for r in cnt["rows"]],
           "top_findings": [{"id": f["finding_id"], "title": f["title"],
                             "severity": refdata.SEVERITY_LABEL.get(f.get("severity"), ""),
                             "fix_priority": refdata.FIX_PRIORITY_LABEL.get(f.get("fix_priority"), "")} for f in top[:8]],
           "root_causes": sorted({f.get("root_cause") for f in data.get("findings", []) if f.get("root_cause")}),
           "objectives": [{"id": o["objective_id"], "title": o["title"],
                           "status": refdata.OBJ_STATUS_LABEL.get(o.get("status"), "")}
                          for o in data.get("objectives", []) if o.get("status") and scenarios]}
    if data.get("findings"):
        tasks.append(_task("write", "summary.overall", "4-1", "summary_overall.md", context=ctx,
                           allowed_ids=[f["finding_id"] for f in data["findings"]] +
                           [o["objective_id"] for o in data.get("objectives", [])], style="ST-02"))
    _caption_tasks(data, tasks, only=None if scenarios else "diag")


def _pentest_tasks(data: dict, tasks: list, todo: list) -> None:
    """모의해킹 보고서(2026-11-18). 사람이 쓴 단계 서술을 다듬고, 2-1 총평만 새로 씀."""
    insts = {i["instance_id"]: i for i in data.get("instances", [])}
    findings = {f["finding_id"]: f for f in data.get("findings", [])}
    for sc in data.get("scenarios", []):
        for s in sc.get("steps", []):
            if not s.get("masked"):
                todo.append({"where": s["step_id"], "what": "마스킹 완료가 꺼져 있어 수행 내용 다듬기를 만들지 않음"})
                continue
            allowed = [s["step_id"]] + s.get("instance_ids", [])
            label, style, note = POLISH_FIELDS["scenario_step.flow"]
            for k, seg in enumerate(s.get("flow") or []):
                if seg.get("text"):
                    tasks.append(_task("polish", "scenario_step.flow", f"{s['step_id']}#{k}", "polish.md",
                                       source=seg["text"], context={"step_id": s["step_id"], "name": s.get("name")},
                                       allowed_ids=allowed, style=style, label=label, note=note))
            if s.get("rationale"):
                label, style, note = POLISH_FIELDS["scenario_step.rationale"]
                tasks.append(_task("polish", "scenario_step.rationale", s["step_id"], "polish.md", source=s["rationale"],
                                   context={"step_id": s["step_id"]}, allowed_ids=allowed, style=style, label=label,
                                   note=note))
    if data.get("scenarios"):
        ctx = {"scenarios": [], "objectives": [{"id": o["objective_id"], "title": o["title"],
                                                "status": refdata.OBJ_STATUS_LABEL.get(o.get("status"), "")}
                                               for o in data.get("objectives", []) if o.get("status")]}
        ids = []
        for sc in data["scenarios"]:
            steps = sc.get("steps", [])
            used = sorted({i for st in steps for i in st.get("instance_ids", [])})
            ids += [sc["scenario_id"]] + used
            ctx["scenarios"].append({
                "id": sc["scenario_id"], "name": sc.get("name"),
                "start": refdata.START_COND_LABEL.get(sc.get("start_condition"), ""),
                "result": sc.get("result_summary") or sc.get("result_summary_auto") or "",
                "steps": {lab: sum(1 for st in steps if (st.get("result") or {}).get("status") == k)
                          for k, lab in refdata.STEP_STATUS_LABEL.items()},
                "used": [{"id": i, "severity": refdata.SEVERITY_LABEL.get((insts.get(i) or {}).get("severity"), ""),
                          "title": (findings.get((insts.get(i) or {}).get("finding_id")) or {}).get("title", "")}
                         for i in used],
                "worked_defense": [p["text"] for p in sc.get("pitfalls", []) if "방어" in (p.get("kind") or "")],
                "causes": sc.get("causes", []),
            })
        tasks.append(_task("write", "pentest.summary", "2-1", "pentest_summary.md", context=ctx,
                           allowed_ids=ids, style="ST-02", label="2-1 총평"))
    _caption_tasks(data, tasks, only="pentest")


def _caption_tasks(data: dict, tasks: list, only: str | None = None) -> None:
    """그림 설명(부록 G·본문 그림 아래)을 같은 형식으로 맞추는 작업. 모든 증거에 만듦.

    - 스크린샷: 그림 앞뒤 문단과 사람이 쓴 캡션을 맥락으로 주고, 설정 ai_read_images가 켜져 있으면
      이미지 파일 경로(task["image"])도 줌. 이미지를 읽을 수 있는 모델(에이전트, API)은 그림을 직접 보고 씀
    - 요청·응답·로그: 마스킹된 내용 앞부분을 맥락으로 줌
    """
    from ..config import settings
    read_images = settings().get("ai_read_images", True)
    owners = {i["instance_id"]: i.get("title", "") for i in data.get("instances", [])}
    owners |= {s["step_id"]: s.get("name", "") for sc in data.get("scenarios", []) for s in sc.get("steps", [])}
    owners |= {t["test_id"]: t.get("procedure", "") for t in (data.get("blue") or {}).get("test_cases", [])}
    for e in data.get("evidence", []):
        owner = (e.get("owner_id") or "").split(":")[0]
        if not e.get("masked") or owner in ("P1", "B1"):   # 구성도는 고정 설명
            continue
        is_scen = bool(re.match(r"^S\d+", owner))
        if (only == "diag" and is_scen) or (only == "pentest" and not is_scen):
            continue   # 그 보고서에 싣지 않는 그림
        ctx = {"evidence_id": e["evidence_id"], "kind": e.get("kind"), "page_id": owner,
               "page_title": owners.get(owner, "")}
        if e.get("caption_src") == "human":
            ctx["human_caption"] = e.get("caption", "")
        near = e.get("near") or {}
        if near.get("before"):
            ctx["text_before_image"] = near["before"]
        if near.get("after"):
            ctx["text_after_image"] = near["after"]
        if e.get("kind") != "screenshot":
            try:
                ctx["content_head"] = Path(e["path"]).read_text(encoding="utf-8")[:800]
            except OSError:
                pass
        t = _task("write", "evidence.caption", e["evidence_id"], "evidence_caption.md", context=ctx,
                  allowed_ids=[e["evidence_id"], owner], style="caption")
        if e.get("kind") == "screenshot" and read_images and e.get("path"):
            t["image"] = str(Path(e["path"]).resolve())
            t["prompt"] += f"\n[이미지]\n{t['image']}\n이 그림 파일을 열어 화면 내용을 직접 확인한 뒤 씀.\n"
        tasks.append(t)


def _blue_tasks(data: dict, tasks: list, todo: list) -> None:
    blue = data.get("blue") or {}
    m = metrics.blue_metrics(blue)
    misses = [t for t in blue.get("test_cases", []) if t.get("status") == "executed" and t.get("outcome") != "invalid"
              and (t.get("outcome") == "not_detected" or (t.get("score") is not None and t["score"] < 3))]
    test_ids = [t["test_id"] for t in blue.get("test_cases", [])]
    agg = {"before": {k: v for k, v in m["before"].items()}, "after": {k: v for k, v in m["after"].items()},
           "misses": [{"test_id": t["test_id"], "procedure": t.get("procedure"), "technique": t.get("technique"),
                       "gap": refdata.GAP_LABEL.get(t.get("gap"), ""), "source_ref": t.get("source_ref")} for t in misses],
           "assets": [{"id": a["asset_id"], "name": a["name"]} for a in data.get("assets", [])]}
    tasks.append(_task("write", "blue.risk_summary", "1-1", "blue_risk_summary.md", context=agg, allowed_ids=test_ids,
                       label="1-1 위험 요약"))
    tasks.append(_task("write", "blue.business_impact", "1-4", "blue_risk_summary.md", context=agg,
                       allowed_ids=test_ids, label="1-4 사업 영향"))
    logs = [{"asset": l.get("asset_id"), "source": l.get("source"), "collected": l.get("collected"),
             "decoder": l.get("decoder")} for l in blue.get("log_sources", [])]
    for t in misses:
        if not t.get("masked"):
            todo.append({"where": t["test_id"], "what": "마스킹 완료가 꺼져 있어 미탐 분석을 만들지 않음"})
            continue
        ctx = {"test_id": t["test_id"], "procedure": t.get("procedure"), "technique": t.get("technique"),
               "expected_observable": t.get("expected_observable"), "gap": t.get("gap"), "score": t.get("score"),
               "log_sources": logs}
        tasks.append(_task("write", "test_case.miss_analysis", t["test_id"], "miss_analysis.md", context=ctx,
                           allowed_ids=[t["test_id"]], style="ST-02a"))
    for fx in blue.get("detection_fixes", []):
        if not fx.get("masked"):
            continue
        ctx = {"fix_id": fx["fix_id"], "goal": fx.get("goal"), "rule_ids": fx.get("rule_ids"),
               "rule_source": fx.get("rule_source", ""), "log_sample": fx.get("log_sample", "")}
        for field, label in (("detection_fix.strategy_abstract", "전략 개요"),
                             ("detection_fix.technical_context", "기술 배경")):
            if fx.get(field.split(".")[1]):
                continue
            if not fx.get("rule_source"):
                todo.append({"where": fx["fix_id"], "what": "본문 「룰 전문」이 비어 있어 전략 개요를 만들 수 없음"})
                break
            tasks.append(_task("write", field, fx["fix_id"], "ads_abstract.md", context=ctx,
                               allowed_ids=[fx["fix_id"]] + fx.get("test_ids", []), style="ST-02a", label=label))
    inc = blue.get("incident")
    if inc and inc.get("timeline"):
        tasks.append(_task("write", "incident.summary", "9", "incident_summary.md", context=inc,
                           allowed_ids=test_ids + [inc.get("scenario_id", "")], style="ST-02a"))
    if blue.get("test_cases"):
        ctx = {"metrics": agg, "fixes": [{"fix_id": f["fix_id"], "name": f.get("name"), "test_ids": f.get("test_ids"),
                                          "after": (f.get("retest") or {}).get("outcome_after")}
                                         for f in blue.get("detection_fixes", [])],
               "blocked_or_detected": [t["test_id"] for t in blue.get("test_cases", [])
                                       if t.get("outcome") in ("blocked", "detected")]}
        tasks.append(_task("write", "blue.lessons", "11", "lessons_learned.md", context=ctx, allowed_ids=test_ids,
                           label="교훈·잘 된 방어"))
    _caption_tasks(data, tasks)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as ex:
            out.append({"task_id": f"?line{n}", "_error": f"JSON 해석 실패: {ex}"})
    return out
