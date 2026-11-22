"""CVSS 3.1 재계산(R-06). 값은 바꾸지 않고 대조만 함."""
from __future__ import annotations


def base_score(vector: str) -> float | None:
    if not vector:
        return None
    try:
        from cvss import CVSS3

        return float(CVSS3(vector).scores()[0])
    except Exception:
        return None
