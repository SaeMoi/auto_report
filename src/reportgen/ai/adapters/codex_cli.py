"""Codex CLI(`codex exec`)로 작업 하나씩 호출."""
from __future__ import annotations

import subprocess

from .base import Adapter


class CodexCLI(Adapter):
    name = "codex_cli"

    def complete(self, prompt: str, task: dict) -> str:
        cmd = self.cfg.get("command", ["codex", "exec", "--skip-git-repo-check"])
        if task.get("image"):   # 그림 설명: 그림을 첨부(codex exec -i)
            cmd = list(cmd) + ["-i", task["image"]]
        r = subprocess.run(cmd + [prompt], capture_output=True, text=True, timeout=self.cfg.get("timeout_sec", 180))
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:300])
        return r.stdout
