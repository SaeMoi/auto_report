"""가져오기 공통 틀(예약)."""
from __future__ import annotations

from pathlib import Path


class Importer:
    name = "base"

    def read(self, path: Path) -> list[dict]:  # pragma: no cover
        raise NotImplementedError
