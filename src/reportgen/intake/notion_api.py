"""2안: 노션 API로 DB·페이지를 읽어 Page 목록으로 만듦(읽기 전용).

- 준비: 노션 통합(integration)을 만들고 대상 DB·페이지에 연결, 토큰을 .env의 NOTION_TOKEN에 둠
- 설치: pip install -e ".[notion]"
- 받은 원본은 input/notion_api.json에 저장해, 다음 실행부터는 네트워크 없이 다시 쓸 수 있음
- 이미지 파일은 input/notion_files/에 내려받음(노션 파일 URL은 1시간 뒤 만료됨)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .pages import Block, Page

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
SINGLE_PAGES = ("B1", "B6", "B10")


class NotionClient:
    def __init__(self, token: str):
        import requests  # 선택 의존성

        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Notion-Version": VERSION,
                               "Content-Type": "application/json"})

    def _post(self, path: str, body: dict) -> dict:
        r = self.s.post(f"{API}{path}", json=body, timeout=60)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = self.s.get(f"{API}{path}", params=params or {}, timeout=60)
        r.raise_for_status()
        return r.json()

    def search(self, query: str, kind: str) -> list[dict]:
        out, cursor = [], None
        while True:
            body = {"query": query, "filter": {"property": "object", "value": kind}, "page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            data = self._post("/search", body)
            out += data["results"]
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    def query_db(self, db_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            body = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            data = self._post(f"/databases/{db_id}/query", body)
            out += data["results"]
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    def children(self, block_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = self._get(f"/blocks/{block_id}/children", params)
            out += data["results"]
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    def download(self, url: str, dest: Path) -> None:
        r = self.s.get(url, timeout=120, headers={"Authorization": None, "Notion-Version": None})
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)


def _rich(rt: list[dict]) -> str:
    out = []
    for t in rt or []:
        s = t.get("plain_text", "")
        if t.get("annotations", {}).get("code"):
            s = f"`{s}`"
        out.append(s)
    return "".join(out)


def prop_to_str(p: dict) -> str:
    t = p.get("type")
    v = p.get(t)
    if v is None:
        return ""
    if t in ("title", "rich_text"):
        return _rich(v)
    if t == "select":
        return v.get("name", "") if v else ""
    if t == "multi_select":
        return ", ".join(x["name"] for x in v)
    if t == "status":
        return v.get("name", "")
    if t == "checkbox":
        return "Yes" if v else "No"
    if t == "number":
        return "" if v is None else str(v)
    if t == "date":
        d = v or {}
        start, end = d.get("start") or "", d.get("end") or ""
        # 범위 날짜(진단 기간·모의해킹 기간)는 "시작 ~ 종료"로 읽음
        return f"{start[:10]} ~ {end[:10]}" if start and end else start
    if t == "people":
        return ", ".join(x.get("name", "") for x in v)
    if t in ("url", "email", "phone_number"):
        return v or ""
    if t == "formula":
        return str(v.get(v.get("type"), "") or "")
    return ""


def _blocks(client: NotionClient, block_id: str, files_dir: Path, depth: int = 0) -> list[Block]:
    out: list[Block] = []
    for b in client.children(block_id):
        t = b["type"]
        v = b.get(t, {})
        if t in ("heading_1", "heading_2", "heading_3"):
            out.append(Block("heading", _rich(v.get("rich_text")), level=int(t[-1])))
        elif t == "paragraph":
            txt = _rich(v.get("rich_text"))
            # 문단 전체가 굵은 글씨면 소제목으로 표시(내보내기와 같게)
            rts = v.get("rich_text") or []
            if rts and all(x.get("annotations", {}).get("bold") for x in rts) and txt.strip():
                txt = f"**{txt.strip()}**"
            out.append(Block("paragraph", txt))
        elif t == "bulleted_list_item":
            out.append(Block("bullet", _rich(v.get("rich_text"))))
        elif t == "numbered_list_item":
            out.append(Block("numbered", _rich(v.get("rich_text"))))
        elif t == "code":
            out.append(Block("code", _rich(v.get("rich_text")), lang=v.get("language", "")))
        elif t == "table":
            rows = []
            for r in client.children(b["id"]):
                rows.append([_rich(c) for c in r["table_row"]["cells"]])
            out.append(Block("table", rows=rows))
        elif t == "image":
            src = v.get(v.get("type"), {}).get("url", "")
            caption = _rich(v.get("caption"))
            ext = re.search(r"\.(png|jpe?g|gif|webp)", src.split("?")[0], re.I)
            dest = files_dir / f"{b['id']}.{ext.group(1).lower() if ext else 'png'}"
            if src and not dest.exists():
                client.download(src, dest)
            out.append(Block("image", caption, path=str(dest)))
            if caption:
                out.append(Block("paragraph", caption))
        if b.get("has_children") and t not in ("table", "child_page", "child_database") and depth < 3:
            out += _blocks(client, b["id"], files_dir, depth + 1)
    return out


def fetch(db_names: dict[str, str], input_dir: Path, token: str | None = None) -> list[Page]:
    token = token or os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN이 없음. .env 또는 환경 변수에 노션 통합 토큰을 넣어 주세요")
    client = NotionClient(token)
    files_dir = input_dir / "notion_files"
    pages: list[Page] = []
    for code, name in db_names.items():
        if code in SINGLE_PAGES:
            hits = [p for p in client.search(name, "page") if _page_title(p) == name]
            for p in hits[:1]:
                pages.append(Page(db=code, title=name, blocks=_blocks(client, p["id"], files_dir), source=p.get("url", "")))
            continue
        dbs = [d for d in client.search(name, "database") if _rich(d.get("title")) == name]
        for d in dbs[:1]:
            for row in client.query_db(d["id"]):
                props = {k: prop_to_str(v) for k, v in row["properties"].items()}
                title = next((prop_to_str(v) for v in row["properties"].values() if v["type"] == "title"), "")
                pages.append(Page(db=code, title=title, props=props,
                                  blocks=_blocks(client, row["id"], files_dir), source=row.get("url", "")))
    dump = input_dir / "notion_api.json"
    dump.write_text(json.dumps([p.to_dict() for p in pages], ensure_ascii=False, indent=1), encoding="utf-8")
    return pages


def _page_title(p: dict) -> str:
    for v in p.get("properties", {}).values():
        if v.get("type") == "title":
            return _rich(v["title"])
    return ""


def load_dump(input_dir: Path) -> list[Page]:
    dump = input_dir / "notion_api.json"
    return [Page.from_dict(d) for d in json.loads(dump.read_text(encoding="utf-8"))]
