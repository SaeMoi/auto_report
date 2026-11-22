"""1안: 노션 「내보내기 → Markdown & CSV(하위 페이지 포함)」 폴더를 Page 목록으로 읽음.

내보내기 구조(노션 기본):
  <DB 이름> <32자리 해시>.csv            ← 속성 (첫 열 = 제목)
  <DB 이름> <32자리 해시>_all.csv        ← 같은 내용(있으면 이쪽 우선)
  <DB 이름> <32자리 해시>/<페이지 제목> <해시>.md   ← 본문
  <페이지 이름> <해시>.md                ← 단독 페이지(B1 관제 환경, B6 침해사고 분석, B10 운영 통계)
압축 파일(.zip)이면 먼저 풀어 둠.
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path

from .pages import Page, clean_text, parse_markdown

HASH_RE = re.compile(r"\s+[0-9a-f]{32}$")
SINGLE_PAGES = ("B1", "B6", "B10")


def strip_hash(stem: str) -> str:
    stem = unicodedata.normalize("NFC", stem)   # Mac 파일 이름은 자모가 풀린 형태(NFD)일 수 있음
    stem = re.sub(r"_all$", "", stem)
    return HASH_RE.sub("", stem).strip()


def _key(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()


def _extract(z: Path, target: Path) -> None:
    """zip 풀기. UTF-8 표시가 없는 zip(일부 압축 프로그램)의 한글 파일 이름이 깨지지 않게 이름을 다시 해석함."""
    with zipfile.ZipFile(z) as zf:
        for info in zf.infolist():
            name = info.filename
            if not info.flag_bits & 0x800:
                try:
                    name = name.encode("cp437").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            name = unicodedata.normalize("NFC", name)
            dest = (target / name).resolve()
            if not str(dest).startswith(str(target.resolve())):   # zip 안의 ../ 경로 차단
                continue
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)


def unzip_cache_dir() -> Path:
    """zip을 풀어 둘 곳. 프로젝트가 OneDrive 안에 있어도 푼 폴더는 동기화되지 않게 밖에 둠(2026-11-21).

    OneDrive 안에서 폴더를 지우고 다시 풀면 클라우드에 옛 한글 이름(NFD)이 남아 「A File Can't Be Synced」가 반복됨.
    환경 변수 REPORTGEN_UNZIP_DIR로 바꿀 수 있음.
    """
    env = os.environ.get("REPORTGEN_UNZIP_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "reportgen" / "unzip"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "reportgen" / "unzip"


def _unzip_in_place(folder: Path) -> None:
    """폴더 안의 zip을 같은 이름 폴더에 풂. zip이 더 새로우면 다시 풀고, zip 안의 zip(노션 대용량 내보내기)도 풂."""
    for _ in range(3):
        todo = []
        for z in folder.rglob("*.zip"):
            target = z.with_suffix("")
            if not target.exists() or target.stat().st_mtime < z.stat().st_mtime:
                todo.append((z, target))
        if not todo:
            return
        for z, target in todo:
            if target.exists():
                shutil.rmtree(target)
            _extract(z, target)
            os.utime(target, None)


def unzip_all(folder: Path) -> list[Path]:
    """폴더 안의 zip(바깥 zip)을 프로젝트 밖 캐시에 풀고, 푼 폴더 목록을 돌려줌.

    캐시 위치: unzip_cache_dir()/<zip 경로 해시>/<zip 이름>. zip이 더 새로우면 다시 풂(캐시 안이라 지워도 됨).
    """
    out: list[Path] = []
    root = unzip_cache_dir()
    for z in sorted(folder.rglob("*.zip")):
        if any(p.suffix == ".zip" for p in z.parents):
            continue
        h = hashlib.sha1(str(z.resolve()).encode("utf-8")).hexdigest()[:12]
        target = root / h / z.stem
        if not target.exists() or target.stat().st_mtime < z.stat().st_mtime:
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            _extract(z, target)
            _unzip_in_place(target)   # zip 안의 zip
            os.utime(target, None)
        out.append(target)
    return out


def _roots(folder: Path) -> list[Path]:
    """읽을 곳: 폴더 자체(예전에 zip 옆에 풀어 둔 같은 이름 폴더는 뺌) + 캐시에 푼 폴더."""
    return [folder] + unzip_all(folder)


def _skip(p: Path, folder: Path) -> bool:
    """zip 옆에 예전 방식으로 풀린 폴더(<이름>.zip 과 같은 이름 폴더) 안의 파일이면 True. 캐시 쪽과 겹치지 않게."""
    try:
        rel = p.relative_to(folder)
    except ValueError:
        return False
    cur = folder
    for part in rel.parts[:-1]:
        cur = cur / part
        if cur.with_name(cur.name + ".zip").exists():
            return True
    return False


def _rel(p: Path, folder: Path) -> str:
    """보고·출처 표시용 상대 경로. 캐시에 푼 파일은 「<zip 이름>/…」로 보임."""
    try:
        return str(p.relative_to(folder))
    except ValueError:
        try:
            return str(Path(*p.relative_to(unzip_cache_dir()).parts[1:]))
        except ValueError:
            return str(p)


def _rglob(folder: Path, pattern: str) -> list[Path]:
    out: list[Path] = []
    for r in _roots(folder):
        out += [p for p in sorted(r.rglob(pattern)) if r != folder or not _skip(p, folder)]
    return out


def _md_title(p: Path) -> str:
    """md 첫 줄의 `# 제목`. 없으면 빈 문자열."""
    try:
        with p.open(encoding="utf-8") as f:
            first = f.readline()
    except (OSError, UnicodeDecodeError):
        return ""
    return first[2:].strip() if first.startswith("# ") else ""


def _md_index(c: Path, db_name: str) -> tuple[dict[str, list[Path]], list[tuple[str, Path]]]:
    """csv 한 개에 딸린 본문 md 찾기.

    노션은 본문 폴더 이름을 `<DB 이름> <해시>`로 주기도 하고 해시 없이 `<DB 이름>`으로 주기도 함.
    파일 이름은 길면 잘리므로, 파일 이름과 md 첫 줄의 제목 둘 다로 찾을 수 있게 함.
    """
    want = _key(db_name)
    dirs = [d for d in c.parent.iterdir() if d.is_dir() and _key(strip_hash(d.name)) == want]
    files: list[Path] = []
    for d in dirs:
        files += sorted(d.rglob("*.md"))
    if not dirs:   # 폴더 이름이 전혀 다르면 csv 옆의 모든 md에서 찾음
        files = sorted(p for p in c.parent.rglob("*.md"))
    by_key: dict[str, list[Path]] = {}
    names: list[tuple[str, Path]] = []
    for p in files:
        fk = _key(strip_hash(p.stem))
        names.append((fk, p))
        by_key.setdefault(fk, []).append(p)
        tk = _key(_md_title(p))
        if tk and tk != fk:
            by_key.setdefault(tk, []).append(p)
    return by_key, names


def _pick(cands: list[Path], row: list[str]) -> Path:
    """제목이 같은 본문이 여럿이면(예: 시나리오마다 「리버스 셸 획득」) 행의 값(단계 ID 등)이 더 많이 든 파일."""
    if len(cands) == 1:
        return cands[0]
    vals = {v.strip() for v in row[1:] if len(v.strip()) >= 4 and len(v.strip()) <= 200}

    def score(p: Path) -> int:
        try:
            head = p.read_text(encoding="utf-8").split("\n## ", 1)[0]
        except (OSError, UnicodeDecodeError):
            return 0
        return sum(1 for v in vals if v in head)
    return max(cands, key=score)


def _find_md(title: str, by_key: dict[str, list[Path]], names: list[tuple[str, Path]], used: set[Path],
             row: list[str] | None = None) -> Path | None:
    k = _key(title)
    if not k:
        return None
    free = [p for p in dict.fromkeys(by_key.get(k, [])) if p not in used]
    if free:
        return _pick(free, row or [])
    # 파일 이름이 잘린 경우: 제목이 파일 이름으로 시작하는 것 중 가장 긴 것
    cands = [(len(fk), p) for fk, p in names if len(fk) >= 8 and k.startswith(fk) and p not in used]
    return max(cands)[1] if cands else None


def read_export(folders: list[Path], db_names: dict[str, str]) -> list[Page]:
    name_to_code = {_key(v): k for k, v in db_names.items()}
    pages: list[Page] = []
    used_md: set[Path] = set()
    seen_csv: set[Path] = set()
    for folder in folders:
        if not folder.exists():
            continue
        csvs = _rglob(folder, "*.csv")
        # 같은 DB의 csv와 _all.csv가 둘 다 있으면 _all 우선
        by_db: dict[str, Path] = {}
        for c in csvs:
            if c.resolve() in seen_csv:
                continue
            seen_csv.add(c.resolve())
            name = strip_hash(c.stem)
            if name not in by_db or c.stem.endswith("_all"):
                by_db[name] = c
        for name, c in by_db.items():
            code = name_to_code.get(_key(name))
            if not code:
                continue
            md_files, md_list = _md_index(c, name)
            with c.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            if not rows:
                continue
            head = [h.strip() for h in rows[0]]
            for r in rows[1:]:
                if not any(x.strip() for x in r):
                    continue
                props = dict(zip([clean_text(h) for h in head], [clean_text(x) for x in r]))
                title = r[0].strip() if r else ""
                md = _find_md(title, md_files, md_list, used_md, r)
                blocks = []
                src = f"{c.name}: {title}"
                if md:
                    used_md.add(md)
                    _, md_props, blocks = parse_markdown(md.read_text(encoding="utf-8"), md.parent)
                    for k, v in md_props.items():
                        props.setdefault(k, v)
                    src = _rel(md, folder)
                pages.append(Page(db=code, title=title, props=props, blocks=blocks, source=src))
        # 단독 페이지
        for md in _rglob(folder, "*.md"):
            if md in used_md or md.resolve() in seen_csv:
                continue
            seen_csv.add(md.resolve())
            if md in used_md:
                continue
            code = name_to_code.get(_key(strip_hash(md.stem)))
            if code in SINGLE_PAGES:
                title, props, blocks = parse_markdown(md.read_text(encoding="utf-8"), md.parent)
                pages.append(Page(db=code, title=title, props=props, blocks=blocks, source=_rel(md, folder)))
    return pages


# ── 팀 와주 페이지의 룰 목록(2026-11-21) ──────────────────────────
# 블루 담당이 없어 B5 「룰 전문」을 더 채울 수 없음. 팀 페이지(「탐지 규칙」 등)의
# 「Rule ID | 탐지 내용 | Level | 대상」 표와 ```xml <rule id=…>``` 블록을 모아 부록 A 요약표로 씀.
_RULE_XML = re.compile(r"<rule\b[^>]*\bid=\"(\d+)\"[\s\S]*?</rule>")


def _strip_md(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)          # <code>, <b> 같은 태그
    s = s.replace("**", "").replace("`", "").replace("\\~", "~").replace("\\", "")
    return s.strip()


def rule_catalog(folders: list[Path]) -> dict[int, dict]:
    """내보내기 폴더의 모든 md에서 커스텀 룰(100000 이상) 요약·XML을 모음. {번호: {desc, level, target, xml, source}}"""
    out: dict[int, dict] = {}
    seen: set[Path] = set()
    for folder in folders:
        if not folder.exists():
            continue
        for md in _rglob(folder, "*.md"):
            if md.resolve() in seen:
                continue
            seen.add(md.resolve())
            try:
                text = md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "Rule ID" not in text and "<rule" not in text:
                continue
            head = None
            for line in text.splitlines():
                if not line.lstrip().startswith("|"):
                    head = None
                    continue
                cells = [_strip_md(c) for c in line.strip().strip("|").split("|")]
                if head is None:
                    if cells and cells[0].lower().replace(" ", "") == "ruleid":
                        head = cells
                    continue
                if set("".join(cells)) <= set("-: "):
                    continue
                m = re.fullmatch(r"(\d{6})", cells[0])
                if not m or int(m.group(1)) < 100000:
                    continue
                row = dict(zip(head, cells))
                rid = int(m.group(1))
                cur = out.setdefault(rid, {"source": md.stem})
                tgt = next((row[k] for k in head[3:] if row.get(k)), "")
                for k, v in (("desc", row.get("탐지 내용", "")), ("level", row.get("Level", "")), ("target", tgt)):
                    if v and not cur.get(k):   # 다른 페이지의 다른 모양 표가 먼저 읽혀도 빈 값은 채움
                        cur[k] = v
            for m in _RULE_XML.finditer(text):
                rid = int(m.group(1))
                if rid >= 100000:
                    out.setdefault(rid, {"source": md.stem}).setdefault("xml", m.group(0))
    return out
