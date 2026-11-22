"""테스트용 어댑터: 다듬기는 원문을 그대로, 작성은 「[AI 작성 예시]」 문장을 돌려줌. 모델을 호출하지 않음."""
from __future__ import annotations

import json

from .base import Adapter


class Fake(Adapter):
    name = "fake"

    def complete(self, prompt: str, task: dict) -> str:
        if task["mode"] == "polish":
            src = task.get("source_text") or ""
            try:
                val = json.loads(src) if src.startswith("[") else src
            except json.JSONDecodeError:
                val = src
            return json.dumps({"text": val, "cited_ids": [], "changes": [], "needs_review": False, "notes": ""},
                              ensure_ascii=False)
        if task["field"] == "evidence.caption":   # 형식 확인용 고정 설명
            kind = (task.get("context") or {}).get("kind")
            noun = {"http": "요청·응답", "log": "로그"}.get(kind, "화면")
            return json.dumps({"text": f"재현 결과 {noun}", "cited_ids": [], "changes": [],
                               "needs_review": False, "notes": ""}, ensure_ascii=False)
        ids = task.get("allowed_ids", [])[:1]
        text = f"[AI 작성 예시] {task['field']} 문장임({ids[0]})" if ids else f"[AI 작성 예시] {task['field']} 문장임"
        if task["field"] in ("test_case.miss_analysis", "blue.lessons"):
            text = [text, text, text] if task["field"] == "test_case.miss_analysis" else [f"교훈: {text}", f"잘 된 방어: {text}"]
        return json.dumps({"text": text, "cited_ids": ids, "changes": [], "needs_review": False, "notes": ""},
                          ensure_ascii=False)
