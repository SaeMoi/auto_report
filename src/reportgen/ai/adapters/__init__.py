"""어댑터 목록. config/models.yaml 의 이름과 같음."""
from .anthropic_api import AnthropicAPI
from .claude_cli import ClaudeCLI
from .codex_cli import CodexCLI
from .fake import Fake
from .manual import Manual
from .openai_api import OpenAIAPI

ADAPTERS = {a.name: a for a in (ClaudeCLI, CodexCLI, AnthropicAPI, OpenAIAPI, Fake, Manual)}


def get(name: str, cfg: dict | None = None):
    if name not in ADAPTERS:
        raise ValueError(f"알 수 없는 어댑터: {name} (가능: {', '.join(ADAPTERS)})")
    return ADAPTERS[name](cfg)
