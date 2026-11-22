"""증거 번호 발급(노션 규격 4-2).

- 처음 발견한 순서대로 E-NNN 발급(레드 E-001~, 블루 E-500~)
- 내용 해시가 같으면 이전 실행과 같은 번호 유지(build/evidence_map.json)
- 파일은 projects/<이름>/evidence/E-NNN.확장자로 복사. 코드 블록 증거는 .txt로 저장
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def _hash(item: dict) -> str:
    h = hashlib.sha256()
    h.update(item["owner_id"].encode())
    if item.get("path") and Path(item["path"]).exists():
        h.update(Path(item["path"]).read_bytes())
    else:
        h.update((item.get("content") or item.get("path") or "").encode())
    return h.hexdigest()[:16]


def assign(raw: list[dict], build_dir: Path, evidence_dir: Path, ranges: dict,
           refmap: dict | None = None) -> tuple[list[dict], list[dict]]:
    """refmap을 주면 증거 참조 키(ref) → 증거 ID를 채움(본문 흐름의 그림 자리 찾기)."""
    map_path = build_dir / "evidence_map.json"
    known: dict[str, str] = json.loads(map_path.read_text(encoding="utf-8")) if map_path.exists() else {}
    nums = [int(v[2:]) for v in known.values()]
    red0, blue0 = ranges.get("red", 1), ranges.get("blue", 500)
    nxt = {"red": max([n for n in nums if n < blue0] + [red0 - 1]) + 1,
           "blue": max([n for n in nums if n >= blue0] + [blue0 - 1]) + 1}
    out, issues = [], []
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for item in raw:
        key = _hash(item)
        eid = known.get(key)
        if not eid:
            n = nxt[item["team"]]
            nxt[item["team"]] = n + 1
            eid = f"E-{n:03d}"
            known[key] = eid
        if refmap is not None and item.get("ref"):
            refmap[item["ref"]] = eid
        if item.get("path"):
            src = Path(item["path"])
            if not src.exists():
                issues.append({"level": "error", "rule": "R-03", "where": item["owner_id"],
                               "msg": f"증거 이미지 파일을 찾지 못함: {src.name}"})
                continue
            dest = evidence_dir / f"{eid}{src.suffix.lower() or '.png'}"
            if not dest.exists():
                shutil.copyfile(src, dest)
        else:
            dest = evidence_dir / f"{eid}.txt"
            dest.write_text(item.get("content", ""), encoding="utf-8")
        out.append({"evidence_id": eid, "kind": item["kind"], "path": str(dest), "caption": item.get("caption", ""),
                    "owner_id": item["owner_id"], "masked": bool(item.get("masked")),
                    "team": item.get("team", "red"),
                    **({"near": item["near"]} if item.get("near") else {})})
    build_dir.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(known, ensure_ascii=False, indent=1), encoding="utf-8")
    # 같은 번호가 두 번 나오면(같은 내용을 두 곳에 붙임) 하나만 남김
    seen, uniq = set(), []
    for e in out:
        if e["evidence_id"] not in seen:
            seen.add(e["evidence_id"])
            uniq.append(e)
    return uniq, issues
