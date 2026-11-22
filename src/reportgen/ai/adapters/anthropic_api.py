"""Anthropic API 어댑터(선택: pip install -e ".[anthropic]")."""
from __future__ import annotations

import os

from .base import Adapter, image_payload


class AnthropicAPI(Adapter):
    name = "anthropic_api"

    def complete(self, prompt: str, task: dict) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ.get(self.cfg.get("api_key_env", "ANTHROPIC_API_KEY")))
        msg = client.messages.create(model=self.cfg.get("model", "claude-opus-5-5"),
                                     max_tokens=self.cfg.get("max_tokens", 2000),
                                     temperature=self.cfg.get("temperature", 0.2),
                                     messages=[{"role": "user", "content": _content(prompt, task)}])
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _content(prompt: str, task: dict):
    """그림 설명 작업이면 그림을 함께 보냄(설정 ai_read_images)."""
    img = image_payload(task["image"]) if task.get("image") else None
    if not img:
        return prompt
    media, b64 = img
    return [{"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}},
            {"type": "text", "text": prompt}]
