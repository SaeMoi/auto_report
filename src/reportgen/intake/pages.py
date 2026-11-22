"""노션 페이지의 중간 표현(Page)과 본문 블록 도구.

내보내기(Markdown & CSV)와 API 두 경로 모두 이 형태로 바꾼 뒤 mapping.py가 읽음.
- props: 속성 이름 → 문자열(체크박스는 "Yes"/"No", 다중 선택·사람은 쉼표 구분)
- blocks: 본문 블록 목록. type ∈ heading, paragraph, bullet, numbered, code, table, image
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    type: str
    text: str = ""
    level: int = 0                 # heading 수준
    lang: str = ""                 # code 언어
    rows: list[list[str]] = field(default_factory=list)   # table: 첫 행 = 머리행
    path: str = ""                 # image: 파일 경로(내보내기 기준 절대 경로) 또는 URL

    def to_dict(self) -> dict:
        d = {"type": self.type, "text": self.text}
        if self.level:
            d["level"] = self.level
        if self.lang:
            d["lang"] = self.lang
        if self.rows:
            d["rows"] = self.rows
        if self.path:
            d["path"] = self.path
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(type=d["type"], text=d.get("text", ""), level=d.get("level", 0),
                   lang=d.get("lang", ""), rows=d.get("rows", []), path=d.get("path", ""))


@dataclass
class Page:
    db: str                        # P1, R1 … (노션 규격 코드)
    title: str
    props: dict[str, str] = field(default_factory=dict)
    blocks: list[Block] = field(default_factory=list)
    source: str = ""               # 원본 위치(오류 메시지용)

    def prop(self, name: str, default: str = "") -> str:
        v = self.props.get(name)
        return v.strip() if isinstance(v, str) and v.strip() else default

    def flag(self, name: str) -> bool:
        return self.prop(name).lower() in ("yes", "true", "예", "참", "checked", "__yes__", "1", "o", "✅")

    def ids(self, name: str) -> list[str]:
        return split_ids(self.prop(name))

    def to_dict(self) -> dict:
        return {"db": self.db, "title": self.title, "props": self.props,
                "blocks": [b.to_dict() for b in self.blocks], "source": self.source}

    @classmethod
    def from_dict(cls, d: dict) -> "Page":
        return cls(db=d["db"], title=d.get("title", ""), props=d.get("props", {}),
                   blocks=[Block.from_dict(b) for b in d.get("blocks", [])], source=d.get("source", ""))

    # ── 본문 찾기 ──────────────────────────────────────────────
    def section(self, title: str, *, within: list[Block] | None = None) -> list[Block]:
        """제목(heading 또는 단독 굵은 글씨 문단)이 title인 곳부터 같은 수준 이상의 다음 제목 전까지."""
        blocks = within if within is not None else self.blocks
        norm = _norm(title)
        start, level = None, 0
        for i, b in enumerate(blocks):
            hl = heading_level(b)
            if start is None:
                if hl and _same(heading_text(b), norm):
                    start, level = i + 1, hl
            elif hl and hl <= level:
                return blocks[start:i]
        return blocks[start:] if start is not None else []

    def has_section(self, title: str, *, within: list[Block] | None = None) -> bool:
        blocks = within if within is not None else self.blocks
        return any(heading_level(b) and _same(heading_text(b), _norm(title)) for b in blocks)


# ── 블록 유틸 ──────────────────────────────────────────────────
BOLD_RE = re.compile(r"^\*\*(.+?)\*\*$")


def heading_level(b: Block) -> int:
    """heading이면 수준, 단독 굵은 글씨 문단이면 9(가장 낮은 제목)로 봄."""
    if b.type == "heading":
        return b.level or 1
    if b.type == "paragraph" and BOLD_RE.match(b.text.strip()):
        return 9
    return 0


def heading_text(b: Block) -> str:
    if b.type == "heading":
        return b.text
    m = BOLD_RE.match(b.text.strip())
    return m.group(1) if m else b.text


def _norm(s: str) -> str:
    s = re.sub(r"[*_`]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.rstrip(":：").strip()


def _same(heading: str, norm_title: str) -> bool:
    """제목 비교. 찾는 제목에 번호가 없으면 「3. 악용 시나리오」처럼 앞에 번호가 붙은 제목도 같은 것으로 봄."""
    h = _norm(heading)
    if h == norm_title:
        return True
    if not re.match(r"^\d+[.)]", norm_title):
        return re.sub(r"^\d+[.)]\s*", "", h) == norm_title
    return False


def text_of(blocks: list[Block]) -> str:
    """문단·목록 블록을 줄 단위 문자열로(코드·표·이미지 제외)."""
    out = []
    for b in blocks:
        if b.type in ("paragraph", "bullet", "numbered") and not heading_level(b):
            out.append(b.text.strip())
    return "\n".join(x for x in out if x)


def list_items(blocks: list[Block]) -> list[str]:
    items = [b.text.strip() for b in blocks if b.type in ("bullet", "numbered") and b.text.strip()]
    if not items:   # 목록 없이 문단으로 쓴 경우 줄 단위로
        items = [b.text.strip() for b in blocks if b.type == "paragraph" and b.text.strip() and not heading_level(b)]
    return items


def first_code(blocks: list[Block]) -> str:
    for b in blocks:
        if b.type == "code":
            return b.text
    return ""


def first_table(blocks: list[Block]) -> list[dict[str, str]]:
    """첫 표를 머리행 기준 dict 목록으로. 머리행만 있으면 빈 목록."""
    for b in blocks:
        if b.type == "table" and b.rows:
            head = [_norm(h) for h in b.rows[0]]
            return [dict(zip(head, [c.strip() for c in r])) for r in b.rows[1:] if any(c.strip() for c in r)]
    return []


def all_tables(blocks: list[Block]) -> list[list[dict[str, str]]]:
    out = []
    for b in blocks:
        if b.type == "table" and b.rows:
            head = [_norm(h) for h in b.rows[0]]
            out.append([dict(zip(head, [c.strip() for c in r])) for r in b.rows[1:] if any(c.strip() for c in r)])
    return out


def kv_table(blocks: list[Block]) -> dict[str, str]:
    """`| 항목 | 값 |` 형태 표를 dict로."""
    out = {}
    for b in blocks:
        if b.type == "table" and b.rows:
            for r in b.rows[1:]:
                if len(r) >= 2:
                    out[_norm(r[0])] = r[1].strip()
            break
    return out


def blocks_to_md(blocks: list[Block]) -> str:
    """본문 블록을 다시 Markdown으로(수행 계획서처럼 사람이 쓴 글을 그대로 옮길 때)."""
    out = []
    for n, b in enumerate(blocks):
        if b.type == "heading":
            out.append("#" * min(6, (b.level or 1) + 2) + " " + b.text)
        elif b.type == "bullet":
            out.append("- " + b.text)
        elif b.type == "numbered":
            out.append("1. " + b.text)
        elif b.type == "code":
            out.append(f"```{b.lang}\n{b.text}\n```")
        elif b.type == "table" and b.rows:
            n = len(b.rows[0])
            out.append("| " + " | ".join(b.rows[0]) + " |")
            out.append("| " + " | ".join(["---"] * n) + " |")
            out += ["| " + " | ".join((r + [""] * n)[:n]) + " |" for r in b.rows[1:]]
        elif b.type == "paragraph":
            if n and blocks[n - 1].type == "image":   # 그림 캡션은 그림과 함께 따로 넣음
                continue
            out.append(b.text)
        else:
            continue
        nxt = blocks[n + 1].type if n + 1 < len(blocks) else ""
        if not (b.type in ("bullet", "numbered") and nxt == b.type):
            out.append("")
    return "\n".join(out).strip()


ID_SPLIT = re.compile(r"[,\s]+")


def split_ids(s: str) -> list[str]:
    return [x for x in ID_SPLIT.split(s or "") if x]


# ── Markdown → 블록 (노션 내보내기용) ───────────────────────────
IMG_RE = re.compile(r"^!\[(.*?)\]\((.+?)\)\s*$")


AUTOLINK_RE = re.compile(r"\[([^\]\n]+)\]\((?:https?://)([^)\s]+?)/?\)")
SCHEME_IN_PATH_RE = re.compile(r"(?<=/)https?://")
# 노션이 「__proto__」 같은 밑줄 두 개 이름을 굵은 글씨로 바꿔 버린 것을 되돌릴 이름들
DUNDERS = ("proto", "init", "dict", "class", "name", "main", "globals", "builtins", "import", "dirname",
           "filename", "defineGetter", "defineSetter", "lookupGetter", "lookupSetter", "construct")


def clean_text(s: str) -> str:
    """노션 내보내기 원문 정리(피드백: 자동 링크·굵은 글씨로 깨진 값).

    - [rule.id](http://rule.id), [soc-reload.sh](http://soc-reload.sh)처럼 글자와 주소가 같은 자동 링크는 글자만 남김
    - 경로 중간에 끼어든 「http://」(…/logs/http://localhost_access_log…)는 뺌
    - **proto** 처럼 밑줄 두 개가 굵은 글씨로 바뀐 이름은 __proto__로 되돌림
    """
    if not s or ("](" not in s and "http" not in s and "**" not in s):
        return s
    s = AUTOLINK_RE.sub(lambda m: m.group(1) if m.group(1).rstrip("/") == m.group(2).rstrip("/") else m.group(0), s)
    s = SCHEME_IN_PATH_RE.sub("", s)
    s = re.sub(r"\*\*(%s)\*\*" % "|".join(DUNDERS), r"__\1__", s)
    return s


def parse_markdown(md: str, base: Path | None = None) -> tuple[str, dict[str, str], list[Block]]:
    """노션 Markdown 페이지 → (제목, 본문 속성, 블록).

    노션 내보내기는 맨 앞에 `# 제목`, 그 다음 `속성: 값` 줄들을 둠. 속성은 CSV가 우선이며 여기 값은 보조용.
    """
    lines = clean_text(md).splitlines()
    title, props, blocks = "", {}, []
    i = 0
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        i = 1
        # 제목 뒤 빈 줄과 「속성: 값」 줄
        while i < len(lines) and not lines[i].strip():
            i += 1
        while i < len(lines) and re.match(r"^[^#|`*!\-\d\s][^:]{0,30}: ", lines[i]):
            k, v = lines[i].split(": ", 1)
            props[k.strip()] = v.strip()
            i += 1
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):   # 구분선
            i += 1
            continue
        if s.startswith("```"):
            lang = s[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            blocks.append(Block("code", "\n".join(buf), lang=lang))
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            blocks.append(Block("heading", m.group(2).strip(), level=len(m.group(1))))
            i += 1
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append([c.replace("\\|", "|") for c in cells])
                i += 1
            blocks.append(Block("table", rows=rows))
            continue
        m = IMG_RE.match(s)
        if m:
            path = m.group(2)
            from urllib.parse import unquote
            path = unquote(path)
            if base is not None and not re.match(r"^https?://", path):
                path = _existing(base / path)
            blocks.append(Block("image", m.group(1), path=path))
            i += 1
            continue
        m = re.match(r"^[-*+]\s+(.*)$", s)
        if m:
            blocks.append(Block("bullet", m.group(1)))
            i += 1
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", s)
        if m:
            blocks.append(Block("numbered", m.group(1)))
            i += 1
            continue
        blocks.append(Block("paragraph", s))
        i += 1
    return title, props, blocks


def _existing(p: Path) -> str:
    """그림 경로. 한글 이름의 유니코드 정규화(맥 NFD ↔ 윈도·리눅스 NFC)가 폴더·파일마다 달라 못 찾는 경우를 맞춤."""
    import unicodedata

    p = p.resolve()
    if p.exists():
        return str(p)
    nfc = lambda x: unicodedata.normalize("NFC", x)   # noqa: E731
    cur = Path(p.anchor)
    for part in p.parts[1:]:
        nxt = cur / part
        if not nxt.exists() and cur.is_dir():
            hit = next((c for c in cur.iterdir() if nfc(c.name) == nfc(part)), None)
            if hit is None:
                return str(p)
            nxt = hit
        cur = nxt
    return str(cur)
