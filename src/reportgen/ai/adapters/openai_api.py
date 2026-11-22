"""OpenAI API 어댑터(선택: pip install -e ".[openai]")."""
from __future__ import annotations

import os

from .base import Adapter, image_payload


class OpenAIAPI(Adapter):
    name = "openai_api"

    def complete(self, prompt: str, task: dict) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get(self.cfg.get("api_key_env", "OPENAI_API_KEY")))
        r = client.chat.completions.create(model=self.cfg.get("model", "gpt-5"),
                                           messages=[{"role": "user", "content": _content(prompt, task)}])
        return r.choices[0].message.content or ""


def _content(prompt: str, task: dict):
    img = image_payload(task["image"]) if task.get("image") else None
    if not img:
        return prompt
    media, b64 = img
    return [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{media};base64,{b64}"}}]
