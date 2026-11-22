"""intake: 입력을 읽어 canonical.json을 만들고 접수 검사 결과(intake_report.md)를 씀."""
from __future__ import annotations

import json
from pathlib import Path

from ..build import merge
from ..config import Project
from ..validate import rules
from . import automask, evidence, notion_api, notion_export
from .mapping import map_pages
from .pages import Page


def load_pages(project: Project, mode: str) -> list[Page]:
    cfg = project.config()
    names = cfg.get("notion_db_names", {})
    if mode == "api":
        dump = project.input / "notion_api.json"
        if dump.exists() and not cfg.get("refresh_api"):
            return notion_api.load_dump(project.input)
        return notion_api.fetch(names, project.input)
    folders = [project.input / "plan", project.input / "notion" / "red", project.input / "notion" / "blue",
               project.input / "notion"]
    return notion_export.read_export(list(dict.fromkeys(folders)), names)


def run(project: Project, mode: str | None = None, report: str | None = None) -> tuple[dict, list[dict]]:
    project.ensure()
    cfg = project.config()
    mode = mode or cfg.get("input_mode", "export")
    canon_in = project.input / "canonical.json"
    if mode == "json" or (canon_in.exists() and mode != "api" and not any((project.input / "notion").glob("**/*.csv"))):
        data = json.loads(canon_in.read_text(encoding="utf-8"))
        issues: list[dict] = []
        # 증거 경로를 프로젝트 기준으로
        for e in data.get("evidence", []):
            p = Path(e["path"])
            if not p.is_absolute():
                e["path"] = str((project.root / p).resolve())
    else:
        pages = load_pages(project, mode)
        mask_issues = automask.apply(pages) if cfg.get("auto_mask", True) else []
        data, issues, raw = map_pages(pages, report, lenient=not cfg.get("strict_input", False))
        if mode != "api" and data.get("blue"):   # 팀 와주 페이지의 룰 요약·XML(부록 A, 2026-11-21)
            cat = notion_export.rule_catalog([project.input / "notion" / "blue", project.input / "notion"])
            data["blue"]["rule_catalog"] = [dict(rule_id=k, **v) for k, v in sorted(cat.items())]
        issues = mask_issues + issues
        refmap: dict[str, str] = {}
        ev, ev_issues = evidence.assign(raw, project.build, project.evidence, cfg.get("evidence_ranges", {}), refmap)
        data["evidence"] = ev
        _resolve_flow(data, refmap)
        default_captions(data)
        issues += ev_issues
    if report:
        data.setdefault("project", {})["report_type"] = report
    data = merge.compute(data)
    issues += rules.run_intake(_schema_view(data), report=report)
    if not cfg.get("strict_input", False):
        issues = [_soften(i) for i in issues]
    issues = _dedupe(issues)
    text = json.dumps(data, ensure_ascii=False, indent=1)
    project.canonical.write_text(text, encoding="utf-8")
    if report:   # 보고서마다 따로 둠: 문서 정보(P1) 행이 보고서 종류마다 달라서, 공용 파일 하나면 마지막 prepare 보고서 것이 남음
        (project.work / report).mkdir(parents=True, exist_ok=True)
        (project.work / report / "canonical.json").write_text(text, encoding="utf-8")
    write_report(project.work / "intake_report.md", issues)
    return data, issues


def _resolve_flow(data: dict, refmap: dict) -> None:
    """본문 흐름의 그림 자리(ref)를 증거 ID로 바꿈. 찾지 못한 그림(파일 없음)은 뺌.
    대상: 취약점 건 상세설명, 시나리오 단계 「수행 내용」, 시나리오 「단서와 경로 선택」"""
    for i in data.get("instances", []):   # 공격 요청 자리의 그림(2026-11-21)
        poc = i.get("poc") or {}
        refs = poc.pop("request_refs", None)
        if refs:
            poc["request_figs"] = [refmap[r] for r in refs if r in refmap]
    holders = [(i, "flow") for i in data.get("instances", [])]
    for sc in data.get("scenarios", []):
        holders.append((sc, "clues"))
        holders += [(st, "flow") for st in sc.get("steps", [])]
    for i, key in holders:
        flow = []
        for seg in i.get(key) or []:
            ref = seg.pop("ref", None)
            if ref:
                eid = refmap.get(ref)
                if "code" not in seg:
                    if eid:
                        flow.append({"evidence_id": eid})
                    continue
                if eid:
                    seg["evidence_id"] = eid
            flow.append(seg)
        if key in i:
            i[key] = flow


DIAGRAM_OWNERS = {"P1": "인프라 구성도", "B1": "관제 환경 구성도"}
KIND_NOUN = {"screenshot": "화면", "http": "요청·응답", "log": "로그", "alert_json": "경보 JSON"}


def default_captions(data: dict) -> None:
    """그림 설명 기본값(AI가 쓰기 전·AI를 안 쓸 때). 형식을 하나로 맞춤: 「<연결 ID> <종류> (n/전체)」.

    노션 캡션(파일 이름이 아닌 것)은 사람이 쓴 설명으로 남겨 두고 caption_src=human으로 표시함.
    """
    by_owner: dict[str, list[dict]] = {}
    for e in data.get("evidence", []):
        by_owner.setdefault((e.get("owner_id") or "").split(":")[0], []).append(e)
    for owner, items in by_owner.items():
        for k, e in enumerate(items, 1):
            if e.get("caption"):
                e.setdefault("caption_src", "human")
                continue
            if owner in DIAGRAM_OWNERS:
                e["caption"], e["caption_src"] = DIAGRAM_OWNERS[owner], "auto"
                continue
            noun = KIND_NOUN.get(e.get("kind"), "증거")
            e["caption"] = f"{owner} {noun}" + (f" ({k}/{len(items)})" if len(items) > 1 else "")
            e["caption_src"] = "auto"


SOFT_RULES = ("R-23", "R-24", "R-25")
OWN_IDS = {("instances", "instance_id"), ("findings", "finding_id"), ("assets", "asset_id"),
           ("objectives", "objective_id"), ("scenarios", "scenario_id")}


def _soften(i: dict) -> dict:
    """완화 기준(strict_input: false): 내용이 덜 채워진 것은 경고로 낮춰 보고서 초안이 먼저 나오게 함.

    ID 누락·중복, 허용되지 않는 선택지, 마스킹 관련 오류는 그대로 오류로 둠.
    """
    if i["level"] != "error":
        return i
    msg = i["msg"]
    empty = ("None is not" in msg or "is too short" in msg or "should be non-empty" in msg
             or "is a required property" in msg or ": '' " in msg)
    path = msg.split(":")[0].split("/")
    own_id = (path[0], path[-1]) in OWN_IDS
    if i["rule"] == "R-20" and ("실행 시각" in msg or "출발지 IP" in msg):   # 2026-11-21: 팀 와주 기록에 없으면 채울 수 없음   # 개선 전 실행 시각 기록이 없는 건: 경고, MTTD에서 빠짐
        return dict(i, level="warning")
    if i["rule"] in SOFT_RULES or (i["rule"] in ("R-01", "R-02", "R-04") and empty and not own_id):
        return dict(i, level="warning")
    return i


def _schema_view(data: dict) -> dict:
    """스키마 검사용: 계산으로 붙인 보조 필드를 그대로 둬도 되게 additionalProperties 없는 부분만 검사."""
    return data


def _dedupe(issues: list[dict]) -> list[dict]:
    seen, out = set(), []
    for i in issues:
        k = (i["level"], i["rule"], i["where"], i["msg"])
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def write_report(path: Path, issues: list[dict]) -> None:
    errs = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] == "warning"]
    lines = ["# 접수 검사 결과 (intake_report)", "",
             f"- 오류 {len(errs)}건, 경고 {len(warns)}건",
             "- 오류가 있으면 보고서를 만들지 않음. 노션에서 해당 페이지를 고친 뒤 다시 내보내 주세요",
             "- 경고는 보고서를 막지 않음. 빈칸은 보고서에 [확인 필요]로 나옴", ""]
    for title, items in (("오류", errs), ("경고", warns)):
        lines.append(f"## {title}")
        lines.append("")
        if not items:
            lines.append("없음")
        else:
            lines.append("| 규칙 | 위치 | 내용 |")
            lines.append("| --- | --- | --- |")
            for i in sorted(items, key=lambda x: (x["where"], x["rule"])):
                lines.append(f"| {i['rule']} | {i['where']} | {i['msg'].replace('|', '/')} |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
