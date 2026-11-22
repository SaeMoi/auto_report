"""표지(첫 쪽). 본문 디자인과 따로 꾸밀 수 있도록 분리함.

Markdown 맨 앞의 「# 제목」과 바로 뒤 「| 항목 | 내용 |」 표(표지 정보)를 받아 첫 쪽을 그림.
표지 정보는 표로 그리지 않고 항목 이름(작은 회색)·값을 격자로 배치함(선은 위쪽 한 줄만).
첫 쪽에는 머리말·쪽 번호가 나오지 않음(reference.docx의 「첫 페이지 다르게」).
표지 모양은 theme.COVER_STYLE로 고름:
  minimal  여백형: 위에 제목, 아래쪽에 표지 정보
  band     왼쪽 띠형: 쪽 왼쪽 끝에 청록 세로 띠, 제목은 가운데쯤
  block    상단 블록형: 쪽 위쪽 40%를 짙은 색 면으로 채우고 그 위에 밝은 글씨 제목
표지만 바꾸려면 이 파일만 고치면 됨. 본문(docx.py)에는 영향 없음.
"""
from __future__ import annotations

import itertools

from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import theme as T

KICKERS = (("계획", "PROJECT PLAN"), ("블루", "BLUE TEAM REPORT"), ("결과", "RESULT REPORT"))
# 표지 정보에서 보여 줄 항목(문서명·프로젝트는 제목·부제로 이미 나옴). (항목, 두 칸 차지 여부)
META = (("작성자 / 검토자", False), ("문서 버전", False))   # 2026-11-17 Kim: 대상·수행 기간은 빼고 이 둘만. 보안 등급은 쪽 아래 작은 글씨로
EMU_CM = 360000
_ids = itertools.count(100)


def _kicker(title: str) -> str:
    for word, label in KICKERS:
        if word in title:
            return label
    return "SECURITY REPORT"


def _split_title(title: str) -> list[str]:
    """긴 제목은 가운데에 가까운 띄어쓰기에서 두 줄로 나눔."""
    if len(title) <= 12 or " " not in title:
        return [title]
    mid = len(title) / 2
    spaces = [i for i, ch in enumerate(title) if ch == " "]
    cut = min(spaces, key=lambda i: abs(i - mid))
    return [title[:cut], title[cut + 1:]]


def _run(par, text: str, size: float, color: str, *, bold: bool = False, tracking: float | None = None):
    from .docx import _set_font, _tracking
    r = par.add_run(text)
    _set_font(r, T.FONT, size)
    r.bold = bold or None
    r.font.color.rgb = RGBColor.from_string(color)
    _tracking(r, T.TRACKING if tracking is None else tracking)
    return r


def _para(container, before: float, after: float, line: float = 1.0, indent_cm: float = 0):
    p = container.add_paragraph()
    pf = p.paragraph_format
    pf.space_before, pf.space_after, pf.line_spacing = Pt(before), Pt(after), line
    if indent_cm:
        pf.left_indent = Cm(indent_cm)
    return p


def _rect(par, x_cm: float, y_cm: float, w_cm: float, h_cm: float, color: str) -> None:
    """쪽 기준 위치에 색 사각형(글 뒤)을 놓음. Word·LibreOffice 모두 그림."""
    n = next(_ids)
    x, y, w, h = (int(v * EMU_CM) for v in (x_cm, y_cm, w_cm, h_cm))
    xml = (
        '<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        '<mc:AlternateContent><mc:Choice Requires="wps"><w:drawing>'
        f'<wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="{n}" behindDoc="1" '
        'locked="1" layoutInCell="1" allowOverlap="1"><wp:simplePos x="0" y="0"/>'
        f'<wp:positionH relativeFrom="page"><wp:posOffset>{x}</wp:posOffset></wp:positionH>'
        f'<wp:positionV relativeFrom="page"><wp:posOffset>{y}</wp:posOffset></wp:positionV>'
        f'<wp:extent cx="{w}" cy="{h}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
        f'<wp:docPr id="{n}" name="표지 도형 {n}"/><wp:cNvGraphicFramePr/>'
        '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        f'<wps:wsp><wps:cNvSpPr/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:ln><a:noFill/></a:ln></wps:spPr><wps:bodyPr/></wps:wsp></a:graphicData></a:graphic>'
        '</wp:anchor></w:drawing></mc:Choice><mc:Fallback/></mc:AlternateContent></w:r>'
    )
    par._p.append(parse_xml(xml))


def _meta_grid(doc, info: dict[str, str], y_cm: float | None, *, x_indent_cm: float = 0,
               label: str = T.MUTED, value: str = T.INK, rule: str = T.INK, note: str = "") -> None:
    """표지 정보: 2칸 격자. 위쪽 선 한 줄, 칸마다 「항목(작은 회색) / 값」. y_cm을 주면 쪽 기준 그 높이에 고정."""
    items = [(k, info[k], wide) for k, wide in META if info.get(k)]
    if not items and not note:
        return
    width = T.CONTENT_WIDTH_CM - x_indent_cm
    t = doc.add_table(rows=0, cols=2)
    t.autofit = False
    tpr = t._tbl.tblPr
    from .docx import _border, _cell_margins
    _border(tpr, "w:tblBorders", {"top": (8, rule), "left": None, "bottom": None, "right": None,
                                  "insideH": None, "insideV": None})
    _cell_margins(tpr, 0, 0)
    if y_cm is not None or x_indent_cm:
        pos = OxmlElement("w:tblpPr")
        pos.set(qn("w:horzAnchor"), "margin")
        pos.set(qn("w:tblpX"), str(int(Cm(x_indent_cm).twips)))
        if y_cm is not None:
            pos.set(qn("w:vertAnchor"), "page")
            pos.set(qn("w:tblpY"), str(int(Cm(y_cm).twips)))
        else:
            pos.set(qn("w:vertAnchor"), "text")
            pos.set(qn("w:tblpY"), "0")
        tpr.insert(0, pos)
    for gc in t._tbl.tblGrid.gridCol_lst:
        gc.w = Cm(width / 2)
    row, col = None, 2
    for key, val, wide in items:
        if wide or col >= 2:
            row = t.add_row()
            col = 0
        cell = row.cells[col]
        if wide:
            cell = cell.merge(row.cells[1])
            col = 2
        else:
            col += 1
        cell.width = Cm(width if wide else width / 2)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(10), Pt(1)
        _run(p, key, 8, label, bold=True, tracking=0.2)
        q = cell.add_paragraph()
        q.paragraph_format.space_before, q.paragraph_format.space_after = Pt(0), Pt(0)
        q.paragraph_format.line_spacing = 1.25
        _run(q, val, 10, value)
    if note:   # 보안 등급 줄: 격자 표의 마지막 줄(따로 띄운 틀은 글꼴이 대체되면 다음 쪽으로 밀려 빈 쪽이 생김)
        cell = t.add_row().cells[0].merge(t.rows[-1].cells[1])
        tcpr = cell._tc.get_or_add_tcPr()
        _border(tcpr, "w:tcBorders", {"top": None})
        p = cell.paragraphs[0]
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(30), Pt(0)
        _run(p, note, 8.5, T.MUTED, tracking=0)
    _tail(doc)


def _tail(doc) -> None:
    """떠 있는 표·틀이 붙을 빈 문단(없으면 다음 쪽 제목에 붙어 2쪽으로 넘어감)."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = pf.space_after = Pt(0)
    pf.line_spacing = Pt(1)


def _footer_note(doc, text: str, y_cm: float, color: str = T.MUTED, x_cm: float = 0) -> None:
    """쪽 아래쪽 작은 글씨(보안 등급 등). 틀(frame)로 위치를 고정함."""
    p = doc.add_paragraph()
    ppr = p._p.get_or_add_pPr()
    fr = OxmlElement("w:framePr")
    for k, v in (("w:w", str(int(Cm(T.CONTENT_WIDTH_CM - x_cm).twips))), ("w:hAnchor", "margin"),
                 ("w:x", str(int(Cm(x_cm).twips))), ("w:vAnchor", "page"), ("w:y", str(int(Cm(y_cm).twips))),
                 ("w:wrap", "around")):
        fr.set(qn(k), v)
    ppr.insert(0, fr)
    _run(p, text, 8.5, color, tracking=0)
    _tail(doc)


def _titles(doc, title, project, *, before, ink=T.INK, kick=T.ACCENT, sub=T.SUB, indent=0, rule=True):
    _run(_para(doc, before, 10, indent_cm=indent), _kicker(title), 10, kick, bold=True, tracking=0.6)
    p = _para(doc, 0, 14, 1.1, indent)
    lines = _split_title(title)
    for n, line in enumerate(lines):
        r = _run(p, line, 30, ink, bold=True, tracking=-1.5)
        if n < len(lines) - 1:
            r.add_break()
    if rule:   # 제목 아래 짧은 강조선
        rp = _para(doc, 0, 12, 1.0, indent)
        _run(rp, "—" * 3, 14, kick, bold=True, tracking=-3)
    if project:
        _run(_para(doc, 0, 0, 1.25, indent), project, 12, sub)


def build(doc, title: str, rows: list[list[str]], table_fn=None, style: str | None = None) -> None:
    """title: 문서 제목, rows: 표지 정보 표(머리행 포함). table_fn은 예전 호출과의 호환용(쓰지 않음)."""
    info = {r[0].strip(): r[1].strip() for r in rows[1:] if len(r) > 1 and r[1].strip()}
    project = info.get("프로젝트", "")
    style = style or getattr(T, "COVER_STYLE", "minimal")
    security = info.get("보안 등급", "")
    note = f"{security}  ·  무단 배포 금지" if security else ""
    if style == "band":
        anchor = _para(doc, 0, 0)
        if T.PAPER:   # 도형이 있는 쪽은 LibreOffice가 배경색을 빼먹는 경우가 있어 바탕을 직접 깖
            _rect(anchor, 0, 0, 21.0, 29.7, T.PAPER)
        _rect(anchor, 0, 0, 1.1, 29.7, T.ACCENT)
        _titles(doc, title, project, before=150, indent=0.6)
        _meta_grid(doc, info, 24.2, x_indent_cm=0.6, note=note)
    elif style == "block":
        anchor = _para(doc, 0, 0)
        if T.PAPER:
            _rect(anchor, 0, 0, 21.0, 29.7, T.PAPER)
        _rect(anchor, 0, 0, 21.0, 12.6, T.INK)
        _rect(anchor, 0, 12.6, 21.0, 0.18, T.ACCENT)
        _titles(doc, title, project, before=70, ink=T.PAPER or "FFFFFF", kick="8FB4BA", sub="B9B6AE")
        _meta_grid(doc, info, 15.0, note=note)
    else:   # minimal
        _titles(doc, title, project, before=110)
        _meta_grid(doc, info, 24.2, note=note)
