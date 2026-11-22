"""ATT&CK Navigator 레이어(JSON). 블루팀 보고서 부록에 첨부함.

색: 탐지·차단 = 초록, 부분 탐지(점수 1~2) = 노랑, 미탐 = 빨강. 같은 기법에 여러 테스트가 있으면 가장 나쁜 결과로 칠함.
"""
from __future__ import annotations

import json
from pathlib import Path

COLOR = {"good": "#8ec843", "partial": "#ffe766", "miss": "#ff6666"}
RANK = {"miss": 0, "partial": 1, "good": 2}


def _grade(t: dict) -> str | None:
    if t.get("status") != "executed" or t.get("outcome") == "invalid":
        return None
    if t.get("outcome") in ("blocked", "detected") and (t.get("score") is None or t["score"] >= 3):
        return "good"
    if t.get("outcome") == "not_detected" or (t.get("score") or 0) == 0:
        return "miss"
    return "partial"


def build(data: dict, phase: str = "after") -> dict:
    blue = data.get("blue") or {}
    worst: dict[str, tuple[str, list[str]]] = {}
    for t in blue.get("test_cases", []):
        tech = (t.get("technique") or "").split()[0] if t.get("technique") else ""
        g = _grade(t if phase == "before" else (t | ((t.get("retest") or {}) if t.get("retest") else {})))
        if not tech or not g:
            continue
        cur = worst.get(tech)
        ids = (cur[1] if cur else []) + [t["test_id"]]
        worst[tech] = (g if not cur or RANK[g] < RANK[cur[0]] else cur[0], ids)
    name = (data.get("project") or {}).get("name", "")
    return {
        "name": f"{name} 탐지 검증 ({'개선 전' if phase == 'before' else '개선 후'})",
        "versions": {"attack": "16", "navigator": "5.1.0", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": "reportgen이 탐지 검증 테스트 케이스(B4)에서 만든 레이어",
        "techniques": [{"techniqueID": k, "color": COLOR[g], "comment": ", ".join(ids), "enabled": True}
                       for k, (g, ids) in sorted(worst.items())],
        "legendItems": [{"label": "탐지·차단", "color": COLOR["good"]}, {"label": "부분 탐지", "color": COLOR["partial"]},
                        {"label": "미탐", "color": COLOR["miss"]}],
        "hideDisabled": False,
    }


def write(data: dict, out_dir: Path) -> list[Path]:
    out = []
    for phase in ("before", "after"):
        p = out_dir / f"attack_layer_{phase}.json"
        p.write_text(json.dumps(build(data, phase), ensure_ascii=False, indent=1), encoding="utf-8")
        out.append(p)
    return out
