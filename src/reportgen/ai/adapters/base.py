"""모델 어댑터 공통. 어댑터는 지시문 문자열을 받아 모델 응답 문자열을 돌려줌."""
from __future__ import annotations

import json
import re


class Adapter:
    name = "base"

    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or {}

    def complete(self, prompt: str, task: dict) -> str:  # pragma: no cover
        raise NotImplementedError


def image_payload(path: str, max_bytes: int = 4_500_000) -> tuple[str, str] | None:
    """그림 파일 → (media_type, base64). API 한도를 넘으면 줄여서 PNG로. 파일이 없으면 None."""
    import base64
    import io
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return None
    data = p.read_bytes()
    media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
             ".webp": "image/webp"}.get(p.suffix.lower())
    if media is None or len(data) > max_bytes:
        from PIL import Image

        im = Image.open(io.BytesIO(data))
        im.thumbnail((1600, 1600))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG")
        data, media = buf.getvalue(), "image/png"
    return media, base64.b64encode(data).decode()


def parse_output(raw: str) -> dict:
    """응답에서 JSON 객체 하나를 꺼냄. 코드 펜스·앞뒤 설명문이 붙어 있어도 첫 객체를 찾음."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"text": "", "needs_review": True, "notes": f"응답을 JSON으로 읽지 못함: {s[:200]}"}
