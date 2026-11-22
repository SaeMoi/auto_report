"""prompts/*.md 를 읽어 작업 하나의 지시문을 만듦. 공통 규칙(_common.md)과 문체 규칙(REPORT_STYLE.md)을 앞에 붙임."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from .. import refdata
from ..config import TOOL_ROOT


@lru_cache
def _read(name: str) -> str:
    text = (TOOL_ROOT / "prompts" / name).read_text(encoding="utf-8")
    return re.sub(r"^<!--.*?-->\s*", "", text, flags=re.S)


def _fill(template: str, values: dict) -> str:
    # {name} 만 치환(JSON 예시의 중괄호는 그대로 둠)
    return re.sub(r"\{([a-z_]+)\}", lambda m: str(values.get(m.group(1), m.group(0))), template)


def build_prompt(template: str, *, context: dict, source=None, **values) -> str:
    style = refdata.style()
    common = _fill(_read("_common.md"), {"style_rules": style.get("_rules_text", "")})
    src = source if isinstance(source, str) else (json.dumps(source, ensure_ascii=False, indent=1) if source else "")
    body = _fill(_read(template), {**values, "context": json.dumps(context, ensure_ascii=False, indent=1),
                                   "source": src})
    return common.strip() + "\n\n" + body.strip() + "\n"
