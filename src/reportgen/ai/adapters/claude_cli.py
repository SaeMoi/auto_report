"""Claude Code CLI(`claude -p`)로 작업 하나씩 호출."""
from __future__ import annotations

import subprocess

from .base import Adapter


class ClaudeCLI(Adapter):
    name = "claude_cli"

    def complete(self, prompt: str, task: dict) -> str:
        cmd = list(self.cfg.get("command", ["claude", "-p", "--output-format", "text"]))
        if task.get("image"):   # 그림 설명: 지시문에 적힌 그림 파일을 Read 도구로 열 수 있게 함
            cmd += ["--allowedTools", "Read"]
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=self.cfg.get("timeout_sec", 180))
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:300])
        return r.stdout
