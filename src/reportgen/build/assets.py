"""자산 ID · 구역 · 서버 · 와주 에이전트 대응(피드백 2026-11-16: 자산 ID - 구역 - 에이전트 통일).

P2 자산의 호스트 칸과 B2 로그 소스의 에이전트 칸(「001 (sesacedu-dmz-web-01)」)을 맞춰 자산마다 에이전트를 하나로 정함.
보고서의 모든 표·문장은 여기서 만든 이름(「A-01 사용자 웹」)과 에이전트를 씀.
"""
from __future__ import annotations

import re

AGENT_RE = re.compile(r"^\s*(\d{3,})\s*(?:\(([^)]+)\))?")


def parse_agent(s) -> tuple[str, str]:
    """「001 (sesacedu-dmz-web-01)」 → ("001", "sesacedu-dmz-web-01"). 형식이 다르면 ("", 원문)."""
    m = AGENT_RE.match(str(s or ""))
    if not m:
        return "", str(s or "").strip()
    return m.group(1), (m.group(2) or "").strip()


def agents(blue: dict) -> dict[str, str]:
    """서버 이름 → 에이전트 번호(로그 소스·모듈에 적힌 에이전트에서 모음)."""
    out: dict[str, str] = {}
    for ls in blue.get("log_sources", []) or []:
        no, host = parse_agent(ls.get("agent"))
        if no and host:
            out.setdefault(host.lower(), no)
    return out


def server_of(asset: dict, known: dict[str, str]) -> str:
    """자산 호스트 칸에서 서버 이름을 찾음. 알려진 에이전트 서버 이름이 들어 있으면 그것, 없으면 괄호 안 이름, 그것도 없으면 원문."""
    host = str(asset.get("host") or "")
    low = host.lower()
    for name in sorted(known, key=len, reverse=True):
        if name and name in low:
            return name
    inner = [x.strip() for x in re.findall(r"\(([^)]*)\)", host) if "-" in x or "." in x]
    if inner:
        return inner[0]
    return re.sub(r"\s*\(.*\)\s*$", "", re.sub(r"^https?://", "", host)).strip()


def asset_map(data: dict) -> dict[str, dict]:
    blue = data.get("blue") or {}
    known = agents(blue)
    out = {}
    for a in data.get("assets", []) or []:
        server = server_of(a, known)
        no = known.get(server.lower(), "")
        out[a["asset_id"]] = {
            "asset_id": a["asset_id"], "name": a.get("name") or "", "zone": a.get("zone"),
            "server": server, "agent_no": no,
            "agent": f"{no} ({server})" if no else "-",
            "label": f"{a['asset_id']} {a.get('name') or ''}".strip(),
        }
    return out


def split_ids(v) -> list[str]:
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in re.split(r"[,\s]+", str(v or "")) if x.strip()]


def mismatches(data: dict) -> list[dict]:
    """로그 소스의 에이전트 서버가 그 자산의 서버와 다른 행(예: A-02인데 에이전트가 웹 서버 001)."""
    amap = asset_map(data)
    out = []
    for ls in (data.get("blue") or {}).get("log_sources", []) or []:
        a = amap.get(ls.get("asset_id"))
        no, host = parse_agent(ls.get("agent"))
        if not a or not no:
            continue
        if host and a["server"] and host.lower() != a["server"].lower():
            owner = next((x for x in amap.values() if x["server"].lower() == host.lower()), None)
            out.append({"source": ls.get("source"), "asset_id": a["asset_id"], "agent": ls.get("agent"),
                        "asset_server": a["server"], "suggest": owner["asset_id"] if owner else None})
    return out
