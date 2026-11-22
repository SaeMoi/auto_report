"""Markdown(render/markdown.py 결과) → DOCX. python-docx로 직접 변환함(docxtpl·pandoc 없이).

지원: 제목(#~####), 문단, 글머리표(-), 번호 목록(1.), 들여쓴 하위 목록, 표(| |), 코드 블록(```),
그림(![설명](경로)), 차트(```chart JSON), 굵게(**), 기울임(*), 인라인 코드(`), 쪽 나눔(<!-- pagebreak -->).
글꼴·여백·스타일은 templates/reference.docx(있으면)에서 가져옴. 없으면 기본 스타일에 맑은 고딕을 씀.
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import cover, theme as T

FONT = T.FONT
MONO = T.MONO
IMG_WIDTH = Cm(15)
SEV_RE = re.compile(r"^(critical|high|medium|low|info)$", re.I)
ID_RE = re.compile(r"^[A-Z]{1,3}\d*-[\w\[\]~\- ]{1,12}$")   # A-01, V-03-1, O-1, X-01, S1-STEP2 …
CAPTION_RE = re.compile(r"^\[(그림|증거|표) [^\]]+\]")
CHAPTER_RE = re.compile(r"^(\d+)\.\s+(.*)$")

# 굵게(**…**)는 앞뒤에 *가 더 붙지 않을 때만. 마스킹 값 「ad***@…」의 ***를 굵게로 읽지 않게 함
INLINE_RE = re.compile(r"((?<!\*)\*\*[^*]+\*\*(?!\*)|`[^`]+`|(?<![\w*])\*[^*\s][^*]*\*(?![\w*]))")
TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
UL_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")


def _set_font(run, name: str = FONT, size: float | None = None) -> None:
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for k in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(k), name)
    if size:
        run.font.size = Pt(size)


def _tracking(run, pt: float) -> None:
    """자간(pt). 음수면 글자 사이가 좁아짐."""
    rpr = run._element.get_or_add_rPr()
    sp = rpr.find(qn("w:spacing"))
    if sp is None:
        sp = OxmlElement("w:spacing")
        rpr.append(sp)
    sp.set(qn("w:val"), str(int(round(pt * 20))))


def _color(run, hex_color: str) -> None:
    run.font.color.rgb = RGBColor.from_string(hex_color)


def _base_styles(doc) -> None:
    for name in ("Normal", "Heading 1", "Heading 2", "Heading 3", "Heading 4", "List Bullet", "List Number"):
        try:
            st = doc.styles[name]
        except KeyError:
            continue
        st.font.name = FONT
        rpr = st.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        for k in ("w:ascii", "w:hAnsi", "w:eastAsia"):
            fonts.set(qn(k), FONT)
        if name.startswith("Heading"):
            st.font.color.rgb = RGBColor.from_string(T.INK)
    doc.styles["Normal"].font.size = Pt(T.BODY)


def _inline(par, text: str, *, bold: bool = False, size: float | None = None, color: str | None = None) -> None:
    start = len(par.runs)
    _inline_runs(par, text, bold=bold, size=size)
    if color:
        for r in par.runs[start:]:
            _color(r, color)


def _inline_runs(par, text: str, *, bold: bool = False, size: float | None = None) -> None:
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = par.add_run(part[2:-2])
            r.bold = True
            _set_font(r, size=size)
        elif part.startswith("`") and part.endswith("`"):
            r = par.add_run(part[1:-1])
            _set_font(r, MONO, size=(size or T.BODY) - 1)
            r._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            r = par.add_run(part[1:-1])
            r.italic = True
            _set_font(r, size=size)
        else:
            r = par.add_run(part)
            r.bold = bold or None
            _set_font(r, size=size)


def _shade(cell, hex_color: str) -> None:
    tcpr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcpr.append(shd)


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    # 「\|」는 칸 구분이 아니라 글자 「|」(정규식 등)
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def _border(parent, tag: str, sides: dict[str, tuple[int, str] | None]) -> None:
    """sides: {"top": (굵기 1/8pt, 색) 또는 None(선 없음)}"""
    box = parent.find(qn(tag))
    if box is None:
        box = OxmlElement(tag)
        parent.append(box)
    for side, spec in sides.items():
        el = OxmlElement(f"w:{side}")
        if spec is None:
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(spec[0]))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), spec[1])
        box.append(el)


def _cell_margins(tpr, top: int, side: int) -> None:
    mar = OxmlElement("w:tblCellMar")
    for name, w in (("top", top), ("left", side), ("bottom", top), ("right", side)):
        m = OxmlElement(f"w:{name}")
        m.set(qn("w:w"), str(w))
        m.set(qn("w:type"), "dxa")
        mar.append(m)
    tpr.append(mar)


_OC = "|".join(sorted(map(re.escape, T.OUTCOME), key=len, reverse=True))
OUTCOME_RE = re.compile(rf"^({_OC})(?:\s*→\s*({_OC}))?(,.*)?$")


def _mark(par, label: str, color: str, size: float) -> None:
    r = par.add_run("■\u00a0")
    _set_font(r, FONT, 7)
    _color(r, color)
    r = par.add_run(label)
    _set_font(r, FONT, size)
    r.bold = True
    _color(r, color)


def _outcome(par, text: str, size: float) -> bool:
    """칸 값이 탐지 결과(차단·탐지·미탐·검증 무효, 「미탐 → 탐지」, 「탐지, 4점」)면 ■ 색 표시."""
    m = OUTCOME_RE.match(text.strip())
    if not m:
        return False
    _mark(par, m.group(1), T.OUTCOME[m.group(1)], size)
    if m.group(2):
        r = par.add_run(" → ")
        _set_font(r, FONT, size)
        _mark(par, m.group(2), T.OUTCOME[m.group(2)], size)
    if m.group(3):
        _inline(par, m.group(3), size=size)
    return True


STAGE_MARK = {"●": (T.OUTCOME["탐지"], 8), "✕": (T.OUTCOME["미탐"], 10), "–": (T.SUB, 9)}


def _stage(par, text: str, size: float) -> bool:
    """단계 표시 칸(● 됨, ✕ 끊김, – 그 뒤): 가운데 정렬, 색으로 구분(블루 5-2 끊김 표)."""
    v = text.strip()
    if v not in STAGE_MARK:
        return False
    color, pt = STAGE_MARK[v]
    r = par.add_run(v)
    _set_font(r, FONT, pt)
    r.bold = v == "✕"
    _color(r, color)
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return True


def _severity(par, text: str, size: float) -> bool:
    """칸 값이 위험도(Critical~Info)면 ■ 표시 + 등급 색 굵은 글씨로 씀. 탐지 결과도 같은 방식."""
    m = SEV_RE.match(text.strip())
    if not m:
        return _outcome(par, text, size)
    color = T.SEVERITY[m.group(1).lower()]
    r = par.add_run("■\u00a0")
    _set_font(r, FONT, 7)
    _color(r, color)
    r = par.add_run(text.strip())
    _set_font(r, FONT, size)
    r.bold = True
    _color(r, color)
    return True


def _table(doc, rows: list[list[str]], *, plain_first_col: bool = False) -> None:
    """표: 위·아래 굵은 검은 선, 머리행 아래 굵은 선, 행 사이 옅은 선, 세로선 없음(디자인 템플릿)."""
    head, body = rows[0], rows[1:]
    ncol = len(head)
    t = doc.add_table(rows=1 + len(body), cols=ncol)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    tpr = t._tbl.tblPr
    _border(tpr, "w:tblBorders", {"top": (12, T.INK), "left": None, "bottom": (12, T.INK), "right": None,
                                  "insideH": (4, T.RULE), "insideV": None})
    _cell_margins(tpr, 70, 110)
    for r, row in enumerate([head] + body):
        row = (row + [""] * ncol)[:ncol]
        first = row[0].strip()
        subtotal = r > 0 and first.endswith("소계")
        total = r > 0 and first in ("합계", "전체", "총계")
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.text = ""
            p = cell.paragraphs[0]
            pf = p.paragraph_format
            pf.space_before = pf.space_after = Pt(0)
            pf.line_spacing = 1.15
            size = T.TABLE_HEAD if r == 0 else T.TABLE_BODY
            if r > 0 and _stage(p, val, size):
                pass
            elif _severity(p, val, size):   # 등급 글자는 한 줄로(줄바꿈 금지)
                cell._element.get_or_add_tcPr().append(OxmlElement("w:noWrap"))
            elif r == 0:
                _inline(p, val, bold=True, size=size, color=T.SUB)
            else:
                bold = subtotal or total or (c == 0 and not plain_first_col and bool(ID_RE.match(first)))
                _inline(p, val, bold=bold, size=size)
            tcpr = cell._element.get_or_add_tcPr()
            if r == 0:
                _border(tcpr, "w:tcBorders", {"bottom": (12, T.INK)})
            elif total:
                _border(tcpr, "w:tcBorders", {"top": (12, T.INK)})
            if subtotal:
                _shade(cell, T.SUBTOTAL)
    _widths(t, [head] + body, ncol, total_cm=T.CONTENT_WIDTH_CM)
    # 머리행 반복
    trpr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trpr.append(th)
    _spacer(doc, 10)


def _disp_len(text: str) -> float:
    """화면 폭 추정: 한글·전각은 2, 나머지 1. 위험도 값은 앞에 ■ 표시가 붙으므로 2칸 더함."""
    if SEV_RE.match(text.strip()):
        return len(text.strip()) + 4
    if OUTCOME_RE.match(text.strip()):
        return _plain_len(text) + 3
    return _plain_len(text)


def _plain_len(text: str) -> float:
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


ID_CELL_RE = re.compile(r"^[A-Z]{1,3}-\d{2,3}(-\d{1,3})?$")


def _widths(t, rows: list[list[str]], ncol: int, total_cm: float = 16.6) -> None:
    """칸 내용 길이에 맞춰 열 폭을 나눔. 짧은 ID 칸은 좁게, 설명 칸은 넓게."""
    need = []
    for c in range(ncol):
        lens = [_disp_len(r[c]) if c < len(r) else 0 for r in rows]
        longest = max(lens) if lens else 1
        avg = sum(lens) / max(1, len(lens))
        need.append(max(4.0, min(60.0, 0.6 * longest + 0.4 * avg)))
    # 최소 폭: 머리글과 짧은 값(ID·등급 등)이 줄바꿈되지 않을 만큼(9pt 기준 한 칸 약 0.19cm)
    mins = []
    for c in range(ncol):
        # 머리글은 띄어쓰기에서 두 줄로 접혀도 됨 → 가장 긴 낱말 기준(「시나리오 사용」은 「시나리오」만큼)
        head = max((_disp_len(w) for w in rows[0][c].split()), default=0) if c < len(rows[0]) else 0
        short = max([_disp_len(r[c]) for r in rows[1:] if c < len(r) and _disp_len(r[c]) <= 10
                     and not SEV_RE.match(r[c].strip())] or [0])
        mins.append(0.2 * max(head if head <= 14 else 8, short) + 0.6)   # 9.5pt 글씨 + 칸 안쪽 여백
    tot = sum(need)
    free = max(0.0, total_cm - sum(mins))
    widths = [m + free * n / tot for m, n in zip(mins, need)]
    scale = total_cm / sum(widths)
    widths = [w * scale for w in widths]
    scale = 1.0
    # 위험도 칸(■ Critical)은 줄바꿈되지 않게 최소 2.6cm 확보. 모자란 만큼 다른 칸들의 여유(1.3cm 넘는 부분)에서 비율대로 덜어 옴
    sev_cols = [c for c in range(ncol) if any(c < len(r) and SEV_RE.match(r[c].strip()) for r in rows[1:])]
    for c in sev_cols:
        mins[c] = max(mins[c], 2.6)
    # ID 칸(V-02, A-01, D-03 …)과 위험도 칸은 접히지 않게 그 폭을 먼저 확보함. 모자라면 다른 칸에서 비율대로 덜어 옴
    # (2026-11-17 리뷰: 9칸 표에서 V-ID가 「V-0 / 2」로 접힘). 다른 칸은 1.2cm까지 줄일 수 있음
    keep = {c: mins[c] for c in sev_cols}
    for c in range(ncol):
        vals = [r[c].strip() for r in rows[1:] if c < len(r) and r[c].strip() not in ("", "-")]
        if vals and all(ID_CELL_RE.match(v) for v in vals):
            keep[c] = 0.2 * max(len(v) for v in vals) + 0.6
    for c, need_w in keep.items():
        lack = need_w - widths[c]
        spare = {i: widths[i] - 1.2 for i in range(ncol) if i not in keep and widths[i] > 1.2}
        room = sum(spare.values())
        if lack > 0 and room > 0:
            take = min(lack, room)
            for i, sp in spare.items():
                widths[i] -= take * sp / room
            widths[c] += take
    t.autofit = False
    grid = t._tbl.tblGrid
    for c, w in enumerate(widths):
        if c < len(grid.gridCol_lst):
            grid.gridCol_lst[c].w = Cm(w * scale)
        for row in t.rows:
            row.cells[c].width = Cm(w * scale)


CODE_FONT = T.MONO          # Windows·Mac Word 기본 포함. 없으면 고정폭 글꼴로 대체됨
CODE_FILL, CODE_EDGE, CODE_LINE = T.CODE_BG, T.CODE_BG, T.CODE_BG


def _spacer(doc, pt: float) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = pf.space_after = Pt(0)
    pf.line_spacing = Pt(pt)
    r = p.add_run("")
    r.font.size = Pt(1)


def _code(doc, lines: list[str]) -> None:
    """코드 블록: 한 칸짜리 표(어두운 바탕, 밝은 고정폭 글씨, 안쪽 여백)로 그림. 앞뒤 간격을 둬 본문과 붙지 않게 함."""
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    _spacer(doc, 4)
    t = doc.add_table(rows=1, cols=1)
    tbl = t._tbl
    tpr = tbl.tblPr
    ind = OxmlElement("w:tblInd")
    ind.set(qn("w:w"), "0")
    ind.set(qn("w:type"), "dxa")
    tpr.append(ind)
    borders = OxmlElement("w:tblBorders")
    for side, color, size in (("top", CODE_LINE, 4), ("bottom", CODE_LINE, 4), ("right", CODE_LINE, 4),
                              ("left", CODE_EDGE, 4)):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), str(size))
        b.set(qn("w:color"), color)
        borders.append(b)
    tpr.append(borders)
    mar = OxmlElement("w:tblCellMar")
    for side, cm in (("top", 0.25), ("bottom", 0.25), ("left", 0.35), ("right", 0.35)):
        m = OxmlElement(f"w:{side}")
        m.set(qn("w:w"), str(int(Cm(cm).twips)))
        m.set(qn("w:type"), "dxa")
        mar.append(m)
    tpr.append(mar)
    cell = t.rows[0].cells[0]
    t.autofit = False
    tw = OxmlElement("w:tblW")
    box_cm = T.CONTENT_WIDTH_CM + 0.7   # 안쪽 여백만큼 좌우로 살짝 내어 본문 글자와 코드 글자 줄을 맞춤
    tw.set(qn("w:w"), str(int(Cm(box_cm).twips)))
    tw.set(qn("w:type"), "dxa")
    old = tpr.find(qn("w:tblW"))
    if old is not None:
        tpr.remove(old)
    tpr.append(tw)
    t._tbl.tblGrid.gridCol_lst[0].w = Cm(box_cm)
    cell.width = Cm(box_cm)
    _shade(cell, CODE_FILL)
    p = cell.paragraphs[0]
    pf = p.paragraph_format
    pf.space_before = pf.space_after = Pt(0)
    pf.line_spacing = 1.25
    for n, line in enumerate(lines or [""]):
        r = p.add_run(line.replace("\t", "    "))
        _set_font(r, CODE_FONT, T.CODE)
        r._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)   # 코드 속 한글은 본문 글꼴
        _tracking(r, 0)
        _color(r, T.CODE_DIM if "[마스킹]" in line or line.lstrip().startswith(("#", "//")) else T.CODE_FG)
        if n < len(lines) - 1:
            r.add_break()
    _spacer(doc, 6)


def _box_table(doc, ncol: int, widths_cm: list[float]):
    t = doc.add_table(rows=1, cols=ncol)
    t.autofit = False
    for c, w in enumerate(widths_cm):
        t._tbl.tblGrid.gridCol_lst[c].w = Cm(w)
        t.rows[0].cells[c].width = Cm(w)
    return t


def _callout(doc, lines: list[str]) -> None:
    """요점 상자(:::요점 … :::): 옅은 바탕 + 왼쪽 청록 굵은 선. 첫 줄은 굵게, 「- 」 줄은 작은 점 목록."""
    _spacer(doc, 4)
    t = _box_table(doc, 1, [T.CONTENT_WIDTH_CM])
    tpr = t._tbl.tblPr
    _border(tpr, "w:tblBorders", {"top": None, "left": (24, T.ACCENT), "bottom": None, "right": None,
                                  "insideH": None, "insideV": None})
    _cell_margins(tpr, 130, 220)
    cell = t.rows[0].cells[0]
    _shade(cell, T.CALLOUT_BG)
    body = [x.strip() for x in lines if x.strip()]
    for n, text in enumerate(body):
        p = cell.paragraphs[0] if n == 0 else cell.add_paragraph()
        pf = p.paragraph_format
        pf.space_before, pf.space_after, pf.line_spacing = Pt(0 if n == 0 else 3), Pt(0), 1.45
        if text.startswith("- "):
            pf.left_indent, pf.first_line_indent = Cm(0.45), Cm(-0.3)
            r = p.add_run("·  ")
            _set_font(r, FONT, T.BODY)
            _color(r, T.ACCENT)
            _inline(p, text[2:])
        else:
            _inline(p, text, bold=(n == 0), size=(T.BODY + 0.5 if n == 0 else None))
    _spacer(doc, 10)


def _text_cm(text: str, size: float) -> float:
    """대략의 글자 폭(cm). 한글·전각은 글자 크기만큼, 숫자·영문·기호는 0.62배(굵게, 대체 글꼴 여유 포함)."""
    pt = sum(size if ord(ch) > 0x2E7F else size * 0.62 for ch in text)
    return pt / 72 * 2.54


def _stat_widths(values: list[str], size: float) -> tuple[list[float], float]:
    """지표 칸 폭: 값이 한 줄에 들어가게 긴 값의 칸을 넓히고, 그래도 넘치면 글자를 줄임(최소 13pt).
    (2026-11-17 리뷰: 「30.8 → 69.2%」가 두 줄로 접힘)"""
    total, n, pad = T.CONTENT_WIDTH_CM, len(values), 0.65   # pad: 칸 안쪽 여백(좌우 160twip)+여유
    while True:
        need = [_text_cm(v, size) + pad for v in values]
        if sum(need) <= total or size <= 13:
            break
        size -= 1
    extra = max(total - sum(need), 0)
    floor = total / n
    # 남는 폭은 원래 균등 폭에 모자란 칸부터 채우고, 나머지는 고르게 나눔
    short = [max(floor - w, 0) for w in need]
    if sum(short) and extra:
        k = min(1.0, extra / sum(short))
        need = [w + s * k for w, s in zip(need, short)]
        extra = max(total - sum(need), 0)
    need = [w + extra / n for w in need]
    return need, size


def _stats(doc, lines: list[str]) -> None:
    """핵심 숫자 줄(:::지표 … :::): 「값 | 이름」 한 줄에 하나, 가로로 나란히 큰 숫자 + 작은 이름."""
    items = [[x.strip() for x in ln.split("|", 1)] for ln in lines if ln.strip()]
    if not items:
        return
    n = len(items)
    widths, size = _stat_widths([it[0] for it in items], 17)
    t = _box_table(doc, n, widths)
    tpr = t._tbl.tblPr
    _border(tpr, "w:tblBorders", {"top": (8, T.INK), "left": None, "bottom": (4, T.RULE), "right": None,
                                  "insideH": None, "insideV": (4, T.RULE)})
    _cell_margins(tpr, 110, 160)
    for c, it in enumerate(items):
        cell = t.rows[0].cells[c]
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(it[0])
        _set_font(r, FONT, size)
        r.bold = True
        _color(r, T.ACCENT)
        _tracking(r, -0.5)
        q = cell.add_paragraph()
        q.paragraph_format.space_after = Pt(0)
        q.paragraph_format.line_spacing = 1.2
        _inline(q, it[1] if len(it) > 1 else "", size=8.5, color=T.SUB)
    _spacer(doc, 10)


def _info(doc, lines: list[str]) -> None:
    """정보 블록(:::정보 … :::): 「항목 :: 값」 한 줄에 하나. 왼쪽 회색 항목명, 오른쪽 값, 행 사이 옅은 선."""
    # 「 :: 값」처럼 항목명이 빈 줄은 바로 위 항목의 값에 줄을 바꿔 이어 붙임(여러 줄 값, 예: 테스트 계정)
    rows: list[list[str]] = []
    for ln in lines:
        if not ln.strip():
            continue
        row = [x.strip() for x in ln.split("::", 1)]
        if rows and len(row) > 1 and not row[0]:
            rows[-1].append(row[1])
        else:
            rows.append(row)
    if not rows:
        return
    label_w = 3.6
    t = doc.add_table(rows=len(rows), cols=2)
    t.autofit = False
    t._tbl.tblGrid.gridCol_lst[0].w = Cm(label_w)
    t._tbl.tblGrid.gridCol_lst[1].w = Cm(T.CONTENT_WIDTH_CM - label_w)
    tpr = t._tbl.tblPr
    _border(tpr, "w:tblBorders", {"top": (4, T.RULE), "left": None, "bottom": (4, T.RULE), "right": None,
                                  "insideH": (4, T.RULE), "insideV": None})
    _cell_margins(tpr, 60, 0)
    for r, row in enumerate(rows):
        a, b = t.rows[r].cells
        a.width, b.width = Cm(label_w), Cm(T.CONTENT_WIDTH_CM - label_w)
        for cell, text, kw in ((a, row[0], {"bold": True, "size": 9, "color": T.SUB}),
                               (b, row[1] if len(row) > 1 else "", {"size": T.TABLE_BODY})):
            p = cell.paragraphs[0]
            pf = p.paragraph_format
            pf.space_before = pf.space_after = Pt(0)
            pf.line_spacing = 1.3
            if cell is b and _severity(p, text, T.TABLE_BODY):
                continue
            _inline(p, text, **kw)
        for more in row[2:]:   # 이어 붙인 줄: 같은 칸에 문단을 하나씩 더함
            q = b.add_paragraph()
            qf = q.paragraph_format
            qf.space_before = qf.space_after = Pt(0)
            qf.line_spacing = 1.3
            _inline(q, more, size=T.TABLE_BODY)
    _spacer(doc, 10)


BLOCKS = {"요점": _callout, "지표": _stats, "정보": _info}


def _img_border(shape) -> None:
    """사진 겉에 얇은 선(theme.IMG_BORDER). 그림 자체의 윤곽선(a:ln)이라 Word·LibreOffice 모두 그대로 그림."""
    color = getattr(T, "IMG_BORDER", None)
    if not color:
        return
    sppr = shape._inline.graphic.graphicData.pic.spPr
    ln = OxmlElement("a:ln")
    ln.set("w", str(int(getattr(T, "IMG_BORDER_PT", 0.5) * 12700)))
    fill = OxmlElement("a:solidFill")
    clr = OxmlElement("a:srgbClr")
    clr.set("val", color)
    fill.append(clr)
    ln.append(fill)
    sppr.append(ln)


def _image(doc, alt: str, src: str, base: Path) -> None:
    path = Path(src)
    if not path.is_absolute():
        path = (base / path).resolve()
    if path.exists():
        try:
            shape = doc.add_picture(str(path), width=IMG_WIDTH)
            _img_border(shape)
            return
        except Exception:  # 손상된 이미지 등
            pass
    p = doc.add_paragraph()
    _inline(p, f"[그림 없음: {alt}]")


def _list_item(doc, text: str, ordered: bool, level: int, number: str | None) -> None:
    """글머리표는 List Bullet 스타일, 번호 목록은 번호를 직접 씀(Word 번호가 문서 전체로 이어지는 문제 회피)."""
    if ordered:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.7 * (level + 1))
        pf.first_line_indent = Cm(-0.5)
        pf.space_after = Pt(2)
        _inline(p, f"{number}. {text}")
        return
    style = "List Bullet" + (f" {min(level + 1, 3)}" if level else "")
    try:
        p = doc.add_paragraph(style=style)
    except KeyError:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.7 * (level + 1))
        text = "• " + text
    p.paragraph_format.space_after = Pt(2)
    _inline(p, text)


def _header_title(doc, title: str) -> None:
    """머리말 왼쪽 문서 제목을 이 보고서 제목으로 바꿈(reference.docx의 첫 글자 칸)."""
    if not title:
        return
    for s in doc.sections:
        for p in s.header.paragraphs:
            for r in p.runs:
                if r.text and r.text != T.SECURITY_LABEL:
                    r.text = title
                    return


def convert(md_text: str, out_path: Path, *, base_dir: Path, reference: Path | None = None) -> Path:
    use_ref = bool(reference and reference.exists())
    doc = Document(str(reference)) if use_ref else Document()
    if use_ref:   # 원본의 본문은 지우고 스타일·머리글·바닥글만 씀
        body = doc.element.body
        for el in list(body):
            if el.tag != qn("w:sectPr"):
                body.remove(el)
    else:
        _base_styles(doc)
        for s in doc.sections:
            s.left_margin = s.right_margin = Cm(2.2)
            s.top_margin = s.bottom_margin = Cm(2.0)
    lines = md_text.splitlines()
    i, para = 0, []
    grouped, break_next = False, False
    title = ""
    # 맨 앞 「# 제목」 + 표지 정보 표 → 표지(cover.py)
    j = 0
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j < len(lines) and re.match(r"^#\s+", lines[j].strip()):
        title = lines[j].strip()[1:].strip()
        k = j + 1
        while k < len(lines) and not lines[k].strip():
            k += 1
        rows = []
        if k + 1 < len(lines) and lines[k].strip().startswith("|") and TABLE_SEP_RE.match(lines[k + 1].strip()):
            rows = [_split_row(lines[k])]
            k += 2
            while k < len(lines) and lines[k].strip().startswith("|"):
                rows.append(_split_row(lines[k]))
                k += 1
        else:
            k = j + 1
        cover.build(doc, title, rows, _table)
        i = k
    _header_title(doc, title)

    def flush():
        if para:
            p = doc.add_paragraph()
            text = " ".join(x.strip() for x in para)
            if CAPTION_RE.match(text):   # 「[그림 E-001] 설명」 캡션 줄: 작은 회색 글씨
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(10)
                _inline(p, text, size=T.CAPTION, color=T.SUB)
            elif text.startswith("**"):   # 「**D-03. …**」 같은 굵은 소제목 줄: 앞 항목과 띄우고 다음 내용과 한 쪽에
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.keep_with_next = True
                _inline(p, text, size=11)   # 본문 10pt보다 살짝 크게
            else:
                _inline(p, text)
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            flush()
            kind = s[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            if kind == "chart":   # Word 기본 차트(render/chart.py)
                from . import chart
                chart.add(doc, "\n".join(buf))
            else:
                _code(doc, buf)
            i += 1
            continue
        if s.startswith(":::") and s[3:].strip() in BLOCKS:
            flush()
            kind = s[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and lines[i].strip() != ":::":
                buf.append(lines[i])
                i += 1
            BLOCKS[kind](doc, buf)
            i += 1
            continue
        if s == "<!-- chapters: grouped -->":   # 장마다 새 쪽 대신, <!-- pagebreak --> 다음 장만 새 쪽
            grouped, break_next = True, True   # 표지 다음 첫 장은 새 쪽
            i += 1
            continue
        if s == "<!-- pagebreak -->":
            flush()
            if grouped:
                break_next = True
            else:
                doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            i += 1
            continue
        if s.startswith("<!--"):
            i += 1
            continue
        if not s:
            flush()
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            level = len(m.group(1))
            h = doc.add_heading(level=0 if level == 1 else min(level - 1, 4))
            if level == 2 and grouped:
                h.paragraph_format.page_break_before = break_next
                if not break_next:
                    h.paragraph_format.space_before = Pt(30)
                break_next = False
            cm = CHAPTER_RE.match(m.group(2)) if level == 2 else None
            if cm:   # 「1. 개요」 → 장 번호만 강조색 「1  개요」
                r = h.add_run(cm.group(1))
                _color(r, T.ACCENT)
                _inline(h, "  " + cm.group(2))
            else:
                _inline(h, m.group(2))
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1].strip()):
            flush()
            rows = [_split_row(s)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            _table(doc, rows)
            continue
        m = IMG_RE.match(s)
        if m:
            flush()
            _image(doc, m.group(1), m.group(2), base_dir)
            i += 1
            continue
        m = OL_RE.match(line) or UL_RE.match(line)
        if m:
            flush()
            ordered = bool(OL_RE.match(line))
            indent = len(m.group(1).replace("\t", "  "))
            text = m.group(3) if ordered else m.group(2)
            # 다음 줄이 들여쓴 이어지는 문장이면 붙임
            while i + 1 < len(lines) and lines[i + 1].startswith(" " * (indent + 2)) and lines[i + 1].strip() \
                    and not (OL_RE.match(lines[i + 1]) or UL_RE.match(lines[i + 1])):
                i += 1
                text += " " + lines[i].strip()
            _list_item(doc, text, ordered, indent // 2, m.group(2) if ordered else None)
            i += 1
            continue
        if s.startswith(">"):
            flush()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            _inline(p, s.lstrip("> "))
            i += 1
            continue
        if s.startswith("※"):   # 「※ …」 안내는 한 줄씩(이어 붙이면 여러 안내가 한 문단으로 뭉침)
            flush()
            para.append(s)
            flush()
            i += 1
            continue
        para.append(s)
        i += 1
    flush()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
