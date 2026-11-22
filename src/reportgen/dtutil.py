"""시각 문자열 읽기. 시간대가 없는 값(날짜만 적은 값 등)은 KST(+09:00)로 봄.

노션에서 날짜만 적은 값(「2026-11-13」)과 시각까지 적은 값(「…+09:00」)이 섞여 있어도
서로 비교·뺄셈이 되게 함.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def parse_dt(s) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except (TypeError, ValueError):
        return None
    if d is not None and d.tzinfo is None:
        d = d.replace(tzinfo=KST)
    return d
