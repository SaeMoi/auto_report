"""수동 어댑터: 지시문을 work/manual_prompts/<task>.md로 써 두고, 사람이 다른 도구에 붙여 넣어 결과를 results.jsonl에 적음."""
from __future__ import annotations

from pathlib import Path

from .base import Adapter


class Manual(Adapter):
    name = "manual"

    def complete(self, prompt: str, task: dict) -> str:
        out = Path(self.cfg.get("work_dir", "work")) / "manual_prompts"
        out.mkdir(parents=True, exist_ok=True)
        (out / (task["task_id"].replace(":", "__").replace("/", "_") + ".md")).write_text(prompt, encoding="utf-8")
        return ""
