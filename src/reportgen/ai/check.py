"""AI 결과 검사(R-14, R-15, R-17, R-27)와 잠금(locked.yaml) 적용."""
from __future__ import annotations

import re

import yaml

from .. import refdata

# 한글 조사가 바로 붙어도(예: V-01은) 잡히도록 \b 대신 영숫자 경계만 봄
ID_RE = re.compile(r"(?<![A-Za-z0-9-])(?:V-\d{2}(?:-\d+)?|S\d+-STEP\d+|S\d+|D-\d{2}|F-\d{2}|E-\d{3}|P-\d{2}|O-\d+|A-\d{2}|"
                   r"CWE-\d+|CVE-\d{4}-\d+|A(?:0[1-9]|10))(?![A-Za-z0-9])")
URL_RE = re.compile(r"https?://\S+|(?<![\w])/[A-Za-z0-9_\-./{}?=&%:]+")
NUM_RE = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?(?![A-Za-z0-9])")
CODE_RE = re.compile(r"`([^`]+)`")


def sentences(text: str) -> list[str]:
    # 「~함(V-01-1). 」처럼 문장 끝에 근거 ID 괄호가 붙은 경우도 문장 끝으로 봄
    parts = re.split(r"(?<=[음함됨임])(?:\s?\([^()\n]{1,60}\))?\.\s+|\n+|(?<=[음함됨임])\s*$", text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def _as_text(v) -> str:
    return "\n".join(v) if isinstance(v, list) else (v or "")


def _tokens(text: str) -> dict[str, set]:
    t = text or ""
    codes = {c.strip() for c in CODE_RE.findall(t)}
    return {"id": set(ID_RE.findall(t)), "url": {u.rstrip(".,)") for u in URL_RE.findall(t)},
            "number": set(NUM_RE.findall(CODE_RE.sub(" ", t))), "code": codes}


def check_result(task: dict, res: dict) -> list[dict]:
    out = []
    tid = task["task_id"]
    text = _as_text(res.get("text"))
    if res.get("_error"):
        return [{"level": "error", "rule": "R-15", "where": tid, "msg": res["_error"]}]
    if not text.strip():
        return [{"level": "warning", "rule": "R-17", "where": tid, "msg": "결과 문장이 비어 있음"}]
    st = refdata.style()
    # R-14 문체
    for line in [x for x in re.split(r"\n+", text) if x.strip()]:
        tail = line.strip().rstrip(".")
        for e in st.get("banned_endings", []):
            if tail.endswith(e.rstrip(".")) or line.strip().endswith(e):
                out.append({"level": "warning", "rule": "R-14", "where": tid, "msg": f"금지 종결 「{e}」: {line[-30:]}"})
                break
    for adv in st.get("banned_adverbs", []):
        if re.search(rf"(?<![가-힣]){adv}(?![가-힣])", text) and not re.search(r"\d", text):
            out.append({"level": "warning", "rule": "R-14", "where": tid, "msg": f"근거 수치 없는 부사 「{adv}」"})
    for ph in st.get("redundant_phrases", []):
        if ph in text:
            out.append({"level": "warning", "rule": "R-14", "where": tid, "msg": f"겹치는 표현 「{ph}」"})
    for bad, good in (st.get("glossary") or {}).items():
        if bad in text:
            out.append({"level": "warning", "rule": "R-14", "where": tid, "msg": f"용어 「{bad}」 → 「{good}」"})
    # R-15 인용 ID
    allowed = set(task.get("allowed_ids") or [])
    src_ids = _tokens(task.get("source_text") or "")["id"]
    ctx_ids = set(ID_RE.findall(str(task.get("context"))))
    for i in set(ID_RE.findall(text)):
        if i not in allowed | src_ids | ctx_ids:
            out.append({"level": "warning", "rule": "R-15", "where": tid, "msg": f"입력에 없는 ID 인용: {i}"})
    if task["mode"] == "write" and task["field"] in ("summary.overall", "pentest.summary", "blue.lessons") and not ID_RE.search(text):
        out.append({"level": "warning", "rule": "R-15", "where": tid, "msg": "근거 ID가 없음"})
    # R-17 길이
    spec = task.get("length") or {}
    if "sentences" in spec:
        n = len(sentences(text)) if not isinstance(res.get("text"), list) else len(res["text"])
        a, b = spec["sentences"]
        if not (a <= n <= b):
            out.append({"level": "warning", "rule": "R-17", "where": tid, "msg": f"문장 수 {n}(기준 {a}~{b})"})
        if spec.get("max_chars") and len(text) > spec["max_chars"]:
            out.append({"level": "warning", "rule": "R-17", "where": tid, "msg": f"{len(text)}자(기준 {spec['max_chars']}자 이내)"})
    if "ratio_to_source" in spec and task.get("source_text"):
        r = len(text) / max(1, len(task["source_text"]))
        a, b = spec["ratio_to_source"]
        if not (a <= r <= b):
            out.append({"level": "warning", "rule": "R-17", "where": tid, "msg": f"원문 대비 길이 {r:.0%}(기준 {a:.0%}~{b:.0%})"})
    if "items" in spec and isinstance(res.get("text"), list):
        a, b = spec["items"]
        if not (a <= len(res["text"]) <= b):
            out.append({"level": "warning", "rule": "R-17", "where": tid, "msg": f"항목 {len(res['text'])}개(기준 {a}~{b})"})
    # R-27 다듬기 보존
    if task["mode"] == "polish" and task.get("source_text"):
        src, dst = _tokens(task["source_text"]), _tokens(text)
        dst_all = text
        for kind in ("id", "url", "code", "number"):
            missing = [x for x in src[kind] if x not in dst_all]
            if missing:
                label = {"id": "ID", "url": "경로·URL", "code": "코드", "number": "숫자"}[kind]
                out.append({"level": "warning", "rule": "R-27", "where": tid,
                            "msg": f"원문의 {label}가 바뀌거나 사라짐: {', '.join(sorted(missing)[:5])}"})
    if res.get("needs_review"):
        out.append({"level": "warning", "rule": "R-18", "where": tid, "msg": f"AI가 검토 요청: {res.get('notes', '')}"})
    return out


def load_locked(path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: v for k, v in data.items() if v not in (None, "")}
