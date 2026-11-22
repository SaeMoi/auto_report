"""검토 페이지(work/<보고서>/review.md) — 사람이 한 장으로 확인하는 곳(규격서 5-8 ⑥).

① 입력 오류  ② 사람이 채울 사실  ③ AI 문장(원문 대비)  ④ 경고
"""
from __future__ import annotations

import json
from pathlib import Path

STATUS_LABEL = {"locked": "확정(잠금)", "ai": "AI 결과(검토 필요)", "pending": "결과 없음"}


def _fmt(v) -> str:
    if v is None:
        return "(없음)"
    if isinstance(v, list):
        return "\n".join(f"{n}. {x}" for n, x in enumerate(v, 1))
    return str(v)


def write(path: Path, *, report: str, intake_issues: list[dict], todo: list[dict], tasks: list[dict],
          results: list[dict], status: dict, ai_issues: list[dict]) -> dict:
    by_id = {r["task_id"]: r for r in results if r.get("task_id")}
    errs = [i for i in intake_issues if i["level"] == "error"]
    warns = [i for i in intake_issues if i["level"] == "warning"] + ai_issues
    ai_by_task: dict[str, list[dict]] = {}
    for i in ai_issues:
        ai_by_task.setdefault(i["where"], []).append(i)
    pending = [t for t in tasks if status.get(t["task_id"]) == "pending"]
    to_review = [t for t in tasks if status.get(t["task_id"]) == "ai"]
    L = [f"# 검토 페이지 — {report} 보고서", "",
         "| 구분 | 건수 | 할 일 |", "| --- | --- | --- |",
         f"| ① 입력 오류 | {len(errs)} | 노션에서 고친 뒤 다시 내보내고 `reportgen prepare` |",
         f"| ② 사람이 채울 사실 | {len(todo)} | 노션에 직접 씀(AI가 채우지 않음) |",
         f"| ③ AI 문장 검토 | {len(to_review)} (결과 없음 {len(pending)}) | 확인 후 `reportgen approve <작업 ID>` 또는 work/<보고서>/locked.yaml에서 고쳐 잠금 |",
         f"| ④ 경고 | {len(warns)} | 확인. v1.0 발행 전 0건 또는 검토자 승인 |", ""]
    L += ["## ① 입력 오류", ""]
    if errs:
        L += ["| 규칙 | 위치 | 내용 |", "| --- | --- | --- |"]
        L += [f"| {i['rule']} | {i['where']} | {i['msg'].replace('|', '/')} |" for i in sorted(errs, key=lambda x: x["where"])]
    else:
        L.append("없음")
    L += ["", "## ② 사람이 채울 사실", ""]
    if todo:
        L += [f"- [ ] {x['where']}: {x['what']}" for x in todo]
    else:
        L.append("없음")
    L += ["", "## ③ AI 문장 (원문 대비)", "",
          "- 「AI 결과」를 확인하고 맞으면 `reportgen approve <작업 ID>`로 잠금. 고칠 문장은 work/<보고서>/locked.yaml에 직접 써서 잠금",
          "- 잠근 문장은 다시 실행해도 바뀌지 않음", ""]
    for t in tasks:
        tid = t["task_id"]
        st = status.get(tid, "pending")
        r = by_id.get(tid, {})
        L.append(f"### {tid} — {STATUS_LABEL[st]}")
        L.append("")
        if t["mode"] == "polish":
            src = t.get("source_text")
            try:
                src_v = json.loads(src) if src and src.startswith("[") else src
            except json.JSONDecodeError:
                src_v = src
            L += ["원문(사람):", "", "```text", _fmt(src_v), "```", ""]
        L += ["AI 결과:" if st != "locked" else "확정 문장:", "", "```text", _fmt(r.get("text")) if st != "pending" else "(결과 없음)", "```"]
        if r.get("changes"):
            L.append("- 바꾼 점: " + "; ".join(r["changes"]))
        if r.get("notes"):
            L.append(f"- AI 메모: {r['notes']}")
        for i in ai_by_task.get(tid, []):
            L.append(f"- ⚠ {i['rule']}: {i['msg']}")
        L.append("")
    L += ["## ④ 경고", ""]
    if warns:
        L += ["| 규칙 | 위치 | 내용 |", "| --- | --- | --- |"]
        L += [f"| {i['rule']} | {i['where']} | {i['msg'].replace('|', '/')} |" for i in warns]
    else:
        L.append("없음")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return {"errors": len(errs), "todo": len(todo), "review": len(to_review), "pending": len(pending), "warnings": len(warns)}
