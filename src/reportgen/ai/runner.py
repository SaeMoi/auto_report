"""프로그램이 직접 모델을 부르는 경로(`reportgen ai --adapter ...`). 기본 경로는 에이전트가 results.jsonl을 씀."""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from . import adapters
from .adapters.base import parse_output
from .tasks import read_jsonl


def run(work: Path, adapter_name: str, only_missing: bool = True, limit: int | None = None) -> int:
    tasks = read_jsonl(work / "tasks.jsonl")
    res_path = work / "results.jsonl"
    done = {r["task_id"] for r in read_jsonl(res_path)} if only_missing else set()
    cfg = (config.models().get("adapters") or {}).get(adapter_name, {}) | {"work_dir": str(work)}
    ad = adapters.get(adapter_name, cfg)
    n = 0
    with res_path.open("a", encoding="utf-8") as f:
        for t in tasks:
            if t["task_id"] in done:
                continue
            if limit is not None and n >= limit:
                break
            try:
                raw = ad.complete(t["prompt"], t)
            except Exception as ex:
                raw = json.dumps({"text": "", "needs_review": True, "notes": f"호출 실패: {ex}"}, ensure_ascii=False)
            if not raw.strip():   # manual 어댑터
                continue
            out = parse_output(raw)
            out = {"task_id": t["task_id"], "mode": t["mode"], **{k: out.get(k) for k in
                                                                  ("text", "cited_ids", "changes", "needs_review", "notes")},
                   "model": adapter_name}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            n += 1
    return n
