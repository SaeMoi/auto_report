"""reportgen 명령.

  reportgen intake  <프로젝트> [--mode export|api|json]
  reportgen prepare <프로젝트> --report plan|diag|pentest|blue  접수 검사 + AI 할 일(work/<보고서>/tasks.jsonl)
  reportgen ai      <프로젝트> --report ... --adapter fake|claude_cli|...   (선택) 프로그램이 모델을 직접 부름
  reportgen check   <프로젝트> --report ...                   AI 결과 검사 + 조립 + 검토 페이지(review.md)
  reportgen approve <프로젝트> --report ... <작업 ID...>|--all  AI 결과를 잠금(locked.yaml)
  reportgen render  <프로젝트> --report ... [--draft]         Markdown → DOCX → PDF

--report를 빼면 all: 진단(diag)·모의해킹(pentest)·블루(blue) 세 권을 각각 만듦. 계획서는 -r plan.
(2026-11-22 옛 한 권짜리 결과 보고서 -r result는 없앰. 노션 P1 「결과 보고서」 행은 diag·pentest가 대신 씀)
<프로젝트>는 projects/<이름> 폴더 경로. 기본 흐름은 prepare → (에이전트가 results.jsonl 작성) → check → approve → render.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import assemble, review
from .ai import check as ai_check
from .ai import runner
from .ai.tasks import make_tasks, read_jsonl, write_jsonl
from .config import TOOL_ROOT, Project
from .intake import check as intake

REPORTS = ("plan", "diag", "pentest", "blue")
ALL = ("diag", "pentest", "blue")   # -r all(기본값): 진단·모의해킹·블루 세 권을 따로 만듦


def _project(path: str) -> Project:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        sys.exit(f"프로젝트 폴더가 없음: {p}")
    return Project(p)


def _work(project: Project, report: str) -> Path:
    w = project.work / report
    w.mkdir(parents=True, exist_ok=True)
    return w


def _load_canonical(project: Project, report: str | None = None) -> dict:
    own = project.work / report / "canonical.json" if report else None   # 보고서별 사본 우선
    if own is not None and own.exists():
        return json.loads(own.read_text(encoding="utf-8"))
    if not project.canonical.exists():
        sys.exit("build/canonical.json이 없음. 먼저 `reportgen prepare`를 실행하세요")
    data = json.loads(project.canonical.read_text(encoding="utf-8"))
    # 보고서별 사본이 없을 때 공용 파일이 다른 보고서로 prepare한 것이면 멈춤
    # (2026-11-21: 블루로 prepare한 상태에서 진단·모의해킹을 check하면 블루 데이터로 조립되던 문제)
    made_for = (data.get("project") or {}).get("report_type")
    if report and made_for and made_for != report:
        sys.exit(f"build/canonical.json은 「{made_for}」 보고서로 prepare한 것임. "
                 f"먼저 `reportgen prepare -r {report}`를 실행하세요")
    return data


def _issues(work: Path) -> list[dict]:
    p = work / "intake_issues.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def cmd_intake(a) -> int:
    pr = _project(a.project)
    _, issues = intake.run(pr, a.mode, a.report)
    errs = sum(1 for i in issues if i["level"] == "error")
    print(f"접수 검사: 오류 {errs}건, 경고 {len(issues) - errs}건 → {pr.work / 'intake_report.md'}")
    return 1 if errs else 0


def cmd_prepare(a) -> int:
    pr = _project(a.project)
    data, issues = intake.run(pr, a.mode, a.report)
    work = _work(pr, a.report)
    (work / "intake_issues.json").write_text(json.dumps(issues, ensure_ascii=False, indent=1), encoding="utf-8")
    tasks, todo = make_tasks(data, a.report)
    write_jsonl(work / "tasks.jsonl", tasks)
    (work / "todo.json").write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
    (work / "results.jsonl").touch()
    if not (work / "locked.yaml").exists():
        (work / "locked.yaml").write_text("# 확정 문장. 작업 ID: 문장(또는 목록). 여기 적은 값은 다시 실행해도 바뀌지 않음\n",
                                          encoding="utf-8")
    summary = _check(pr, a.report, quiet=True)
    errs = sum(1 for i in issues if i["level"] == "error")
    print(f"준비 완료: AI 작업 {len(tasks)}개, 사람이 채울 칸 {len(todo)}개, 입력 오류 {errs}건")
    print(f"  할 일 목록 {work / 'tasks.jsonl'}")
    print(f"  결과 파일 {work / 'results.jsonl'} (에이전트가 작업마다 한 줄씩 씀)")
    print(f"  검토 페이지 {work / 'review.md'}")
    return 1 if errs else 0


def cmd_ai(a) -> int:
    pr = _project(a.project)
    n = runner.run(_work(pr, a.report), a.adapter, only_missing=not a.redo, limit=a.limit)
    print(f"{a.adapter}: {n}개 작업 결과를 results.jsonl에 씀")
    return 0


def _check(pr: Project, report: str, quiet: bool = False) -> dict:
    work = _work(pr, report)
    data = _load_canonical(pr, report)
    tasks = read_jsonl(work / "tasks.jsonl")
    results = read_jsonl(work / "results.jsonl")
    locked = ai_check.load_locked(work / "locked.yaml")
    by_task = {t["task_id"]: t for t in tasks}
    last = {}
    ai_issues = []
    for r in results:
        if r.get("_error"):
            ai_issues.append({"level": "warning", "rule": "R-15", "where": r["task_id"], "msg": r["_error"]})
            continue
        if r.get("task_id") not in by_task:
            ai_issues.append({"level": "warning", "rule": "R-15", "where": str(r.get("task_id")),
                              "msg": "tasks.jsonl에 없는 작업 ID"})
            continue
        last[r["task_id"]] = r
    for tid, r in last.items():
        if tid not in locked:
            ai_issues += ai_check.check_result(by_task[tid], r)
    report_data, status = assemble.assemble(data, tasks, list(last.values()), locked)
    assemble.save(work / "report.json", report_data)
    todo = json.loads((work / "todo.json").read_text(encoding="utf-8")) if (work / "todo.json").exists() else []
    s = review.write(work / "review.md", report=report, intake_issues=_issues(work), todo=todo, tasks=tasks,
                     results=list(last.values()), status=status, ai_issues=ai_issues)
    if not quiet:
        print(f"검토 페이지: {work / 'review.md'}")
        print(f"  입력 오류 {s['errors']} / 사람이 채울 칸 {s['todo']} / AI 검토 {s['review']} "
              f"(결과 없음 {s['pending']}) / 경고 {s['warnings']}")
    return s


def cmd_check(a) -> int:
    s = _check(_project(a.project), a.report)
    return 1 if s["errors"] else 0


def cmd_approve(a) -> int:
    pr = _project(a.project)
    work = _work(pr, a.report)
    path = work / "locked.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    locked = raw or {}
    last = {r["task_id"]: r for r in read_jsonl(work / "results.jsonl") if r.get("task_id") and not r.get("_error")}
    ids = list(last) if a.all else a.task_ids
    n = 0
    for tid in ids:
        r = last.get(tid)
        if not r or r.get("text") in (None, "", []):
            print(f"  건너뜀(결과 없음): {tid}")
            continue
        if tid in locked and not a.force:
            continue
        locked[tid] = r["text"]
        n += 1
    header = "# 확정 문장. 작업 ID: 문장(또는 목록). 여기 적은 값은 다시 실행해도 바뀌지 않음\n"
    path.write_text(header + yaml.safe_dump(locked, allow_unicode=True, sort_keys=True, width=1000), encoding="utf-8")
    print(f"잠금 {n}개 추가 → {path}")
    _check(pr, a.report, quiet=True)
    return 0


def cmd_render(a) -> int:
    from .render import attack_layer, docx, markdown, pdf

    pr = _project(a.project)
    work = _work(pr, a.report)
    s = _check(pr, a.report, quiet=True)
    if s["errors"] and not a.force:
        print(f"입력 오류 {s['errors']}건이 있어 만들지 않음. {work / 'review.md'} ①을 확인하세요 (--force로 무시)")
        return 1
    if not a.draft and (s["pending"] or s["review"]):
        print(f"아직 확정하지 않은 AI 문장이 있음(검토 {s['review']}, 결과 없음 {s['pending']}). "
              "검토 후 `reportgen approve`로 잠그거나, 초안이면 --draft를 붙이세요")
        return 1
    data = json.loads((work / "report.json").read_text(encoding="utf-8"))
    cfg = pr.config()
    ver = (data.get("project") or {}).get("version") or "0.0"   # 버전이 비어 있으면 0.0
    stem = f"{a.report}_v{ver}" + ("_draft" if a.draft else "")
    pr.output.mkdir(parents=True, exist_ok=True)
    md = markdown.render(a.report, data, pr.output)
    # 출력 전 검사: 점수·시각·건수 정합성, 부록 룰 전문, 대기 문구(최종본은 오류가 있으면 만들지 않음)
    from .validate import output as out_check
    oc = out_check.run(a.report, data, md)
    out_check.write(work / "output_check.md", oc, a.draft)
    oc_err = sum(1 for i in oc if i["level"] == "error")
    print(f"출력 전 검사: 오류 {oc_err}건, 경고 {len(oc) - oc_err}건 → {work / 'output_check.md'}")
    if oc_err and not a.draft and not a.force:
        print("오류가 있어 최종본을 만들지 않음(초안은 --draft)")
        return 1
    md_path = pr.output / f"{stem}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Markdown {md_path}")
    formats = a.formats.split(",") if a.formats else (cfg.get("output") or {}).get("formats", ["docx", "pdf"])
    if "docx" in formats or "pdf" in formats:
        ref = (cfg.get("output") or {}).get("docx_reference")
        ref_path = (TOOL_ROOT / ref) if ref else None
        dx = docx.convert(md, pr.output / f"{stem}.docx", base_dir=pr.output, reference=ref_path)
        print(f"DOCX {dx}")
        if "pdf" in formats:
            try:
                pf = pdf.convert(dx, pr.output, (cfg.get("output") or {}).get("libreoffice"))
                print(f"PDF {pf}")
            except Exception as ex:
                print(f"PDF 건너뜀: {ex}")
    if a.report == "blue":
        for p in attack_layer.write(data, pr.output):
            print(f"ATT&CK 레이어 {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reportgen", description="노션 입력 → 검사 → AI 다듬기 → DOCX/PDF 보고서")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, report=True):
        p = sub.add_parser(name)
        p.add_argument("project", help="projects/<이름> 폴더")
        if report:
            p.add_argument("--report", "-r", choices=REPORTS + ("all",), default="all",
                           help="all(기본) = diag·pentest·blue 세 권을 각각 만듦")
        p.set_defaults(fn=fn)
        return p

    p = add("intake", cmd_intake)
    p.add_argument("--mode", choices=["export", "api", "json"])
    p = add("prepare", cmd_prepare)
    p.add_argument("--mode", choices=["export", "api", "json"])
    p = add("ai", cmd_ai)
    p.add_argument("--adapter", "-a", default="fake")
    p.add_argument("--redo", action="store_true", help="결과가 있는 작업도 다시 실행")
    p.add_argument("--limit", type=int)
    add("check", cmd_check)
    p = add("approve", cmd_approve)
    p.add_argument("task_ids", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true", help="이미 잠근 작업도 덮어씀")
    p = add("render", cmd_render)
    p.add_argument("--draft", action="store_true", help="검토 전 초안(미확정 AI 문장 포함)")
    p.add_argument("--force", action="store_true", help="입력 오류가 있어도 만듦")
    p.add_argument("--formats", help="md,docx,pdf 중 쉼표로")
    a = ap.parse_args(argv)
    if getattr(a, "report", None) != "all":
        return a.fn(a) or 0
    if a.cmd == "approve" and a.task_ids:
        sys.exit("작업 ID를 골라 잠글 때는 -r 로 보고서를 하나 정해 주세요(diag, pentest, blue)")
    rc = 0
    for r in ALL:
        print(f"\n===== {r} =====")
        try:
            rc = max(rc, a.fn(argparse.Namespace(**{**vars(a), "report": r})) or 0)
        except SystemExit as ex:   # 한 권이 멈춰도 나머지는 계속 만듦
            print(ex.code if isinstance(ex.code, str) else f"종료 코드 {ex.code}")
            rc = max(rc, ex.code if isinstance(ex.code, int) else 1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
