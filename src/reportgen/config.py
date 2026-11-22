"""설정과 경로. 도구 루트(이 저장소)와 프로젝트 폴더(projects/<이름>)를 다룸."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

TOOL_ROOT = Path(os.environ.get("REPORTGEN_ROOT", Path(__file__).resolve().parents[2]))


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def settings() -> dict:
    return load_yaml(TOOL_ROOT / "config" / "settings.yaml")


def models() -> dict:
    return load_yaml(TOOL_ROOT / "config" / "models.yaml")


@dataclass
class Project:
    """projects/<이름>/ 폴더 구조.

    input/plan, input/notion/red, input/notion/blue : 노션 내보내기
    input/notion_api.json                            : 노션 API로 받은 원본(2안)
    input/canonical.json                             : 정규 데이터를 직접 줄 때(json 모드, 시연·테스트)
    evidence/  build/  work/  output/                : 프로그램이 만드는 폴더
    """

    root: Path

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def input(self) -> Path:
        return self.root / "input"

    @property
    def evidence(self) -> Path:
        return self.root / "evidence"

    @property
    def build(self) -> Path:
        return self.root / "build"

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def canonical(self) -> Path:
        return self.build / "canonical.json"

    def config(self) -> dict:
        base = settings()
        base.update(load_yaml(self.root / "project.yaml"))
        return base

    def ensure(self) -> None:
        for p in (self.evidence, self.build, self.work, self.output):
            p.mkdir(parents=True, exist_ok=True)
