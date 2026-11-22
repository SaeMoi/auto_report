"""Word 기본 차트(막대)를 DOCX에 넣음. matplotlib 같은 추가 설치 없이 차트 XML을 직접 씀.

Markdown에서는 코드 블록 ```chart 안의 JSON으로 표시함(render/markdown.py가 만듦):
  {"title": "탐지율 (%)", "categories": ["개선 전", "개선 후"],
   "series": [{"name": "탐지율", "values": [30.8, 69.2], "colors": ["A6A6A6", "2E75B6"]}],
   "grouping": "clustered"|"stacked", "dir": "col"|"bar", "max": 100, "width_cm": 5.2, "height_cm": 5}
  {"row": [차트, 차트, ...]} 는 표 한 줄에 나란히 놓음.
Word에서 차트로 열리고(색·글꼴 수정 가능), LibreOffice PDF 변환에서도 그대로 그려짐.
데이터 원본(엑셀)은 넣지 않아 Word의 「데이터 편집」은 쓸 수 없음. 값은 노션을 고친 뒤 다시 만듦.
"""
from __future__ import annotations

import json
from xml.sax.saxutils import escape

from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.shared import Cm

CT = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
RT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
NS_C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
from .theme import FONT  # noqa: E402  디자인 글꼴과 같게
PALETTE = ["2F5B63", "B9B6AE", "5E7C5A", "9C3E39", "A88B35", "7B7F86"]   # theme.py 색과 맞춤


def _col(i: int) -> str:
    """0 → B, 1 → C … (엑셀 열 이름. 차트 참조 문자열에만 씀)."""
    return chr(ord("B") + i)


def _num(v) -> str:
    return "" if v is None else (str(int(v)) if float(v).is_integer() else str(round(float(v), 2)))


def _font(sz: int, bold: bool = False, color: str = "404040") -> str:
    b = ' b="1"' if bold else ' b="0"'
    return (f'<a:defRPr sz="{sz}"{b}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:defRPr>')


def _txpr(sz: int, bold: bool = False, color: str = "404040") -> str:
    return f"<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr>{_font(sz, bold, color)}</a:pPr><a:endParaRPr lang=\"ko-KR\"/></a:p></c:txPr>"


def chart_xml(spec: dict) -> str:
    cats = [str(c) for c in spec.get("categories", [])]
    series = spec.get("series", [])
    stacked = spec.get("grouping") == "stacked"
    n = len(cats)
    cat_xml = "".join(f'<c:pt idx="{i}"><c:v>{escape(c)}</c:v></c:pt>' for i, c in enumerate(cats))
    sers = []
    for si, s in enumerate(series):
        col = _col(si)
        color = s.get("color") or PALETTE[si % len(PALETTE)]
        pts = "".join(f'<c:pt idx="{i}"><c:v>{_num(v)}</c:v></c:pt>'
                      for i, v in enumerate(s.get("values", [])) if v is not None and not (stacked and v == 0))
        dpts = "".join(  # 같은 계열 안에서 막대마다 색을 달리할 때(개선 전 회색, 개선 후 파랑)
            f'<c:dPt><c:idx val="{i}"/><c:invertIfNegative val="0"/><c:bubble3D val="0"/>'
            f'<c:spPr><a:solidFill><a:srgbClr val="{c}"/></a:solidFill></c:spPr></c:dPt>'
            for i, c in enumerate(s.get("colors") or []))
        fmt = escape(spec.get("format") or "General", {'"': "&quot;"})
        lbl_pos = "" if stacked else '<c:dLblPos val="outEnd"/>'
        sers.append(
            f'<c:ser><c:idx val="{si}"/><c:order val="{si}"/>'
            f'<c:tx><c:strRef><c:f>Sheet1!${col}$1</c:f><c:strCache><c:ptCount val="1"/>'
            f'<c:pt idx="0"><c:v>{escape(str(s.get("name", "")))}</c:v></c:pt></c:strCache></c:strRef></c:tx>'
            f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></c:spPr>'
            f'<c:invertIfNegative val="0"/>{dpts}'
            f'<c:dLbls><c:numFmt formatCode="{fmt}" sourceLinked="0"/><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'
            f'{_txpr(900, True, "FFFFFF" if stacked else "404040")}{lbl_pos}<c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/>'
            f'<c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>'
            f'<c:cat><c:strRef><c:f>Sheet1!$A$2:$A${n + 1}</c:f><c:strCache><c:ptCount val="{n}"/>{cat_xml}'
            f'</c:strCache></c:strRef></c:cat>'
            f'<c:val><c:numRef><c:f>Sheet1!${col}$2:${col}${n + 1}</c:f><c:numCache><c:formatCode>General</c:formatCode>'
            f'<c:ptCount val="{n}"/>{pts}</c:numCache></c:numRef></c:val></c:ser>')
    scaling = '<c:orientation val="minMax"/>'
    if spec.get("max") is not None:
        scaling += f'<c:max val="{spec["max"]}"/>'
    scaling += '<c:min val="0"/>'
    bar_dir = spec.get("dir", "col")
    cat_pos, val_pos = ("l", "b") if bar_dir == "bar" else ("b", "l")
    legend = (f'<c:legend><c:legendPos val="b"/><c:overlay val="0"/>{_txpr(900)}</c:legend>'
              if spec.get("legend", len(series) > 1) else "")
    title = spec.get("title")
    title_xml = (f'<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr>{_font(1000, True)}</a:pPr>'
                 f'<a:r><a:rPr lang="ko-KR" sz="1000" b="1"/><a:t>{escape(title)}</a:t></a:r></a:p></c:rich></c:tx>'
                 f'<c:overlay val="0"/></c:title><c:autoTitleDeleted val="0"/>'
                 if title else '<c:autoTitleDeleted val="1"/>')
    grid = '<c:majorGridlines><c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="E0E0E0"/></a:solidFill></a:ln></c:spPr></c:majorGridlines>'
    overlap = '<c:overlap val="100"/>' if stacked else ""
    major = f'<c:majorUnit val="{spec["major"]}"/>' if spec.get("major") else ""
    noline = '<c:spPr><a:ln><a:noFill/></a:ln></c:spPr>'
    axline = '<c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="BFBFBF"/></a:solidFill></a:ln></c:spPr>'
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<c:chartSpace xmlns:c="{NS_C}" xmlns:a="{NS_A}" xmlns:r="{NS_R}">'
        f'<c:lang val="ko-KR"/><c:roundedCorners val="0"/>'
        f'<c:chart>{title_xml}<c:plotArea><c:layout/>'
        f'<c:barChart><c:barDir val="{bar_dir}"/><c:grouping val="{"stacked" if stacked else "clustered"}"/>'
        f'<c:varyColors val="0"/>{"".join(sers)}'
        f'<c:gapWidth val="{spec.get("gap", 60)}"/>{overlap}'
        f'<c:axId val="1001"/><c:axId val="1002"/></c:barChart>'
        f'<c:catAx><c:axId val="1001"/><c:scaling><c:orientation val="{"maxMin" if bar_dir == "bar" else "minMax"}"/></c:scaling>'
        f'<c:delete val="0"/><c:axPos val="{cat_pos}"/><c:numFmt formatCode="General" sourceLinked="0"/>'
        f'<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{axline}{_txpr(900)}'
        f'<c:crossAx val="1002"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/>'
        f'<c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
        f'<c:valAx><c:axId val="1002"/><c:scaling>{scaling}</c:scaling><c:delete val="{1 if spec.get("hide_axis") else 0}"/>'
        f'<c:axPos val="{val_pos}"/>{grid}<c:numFmt formatCode="General" sourceLinked="0"/>'
        f'<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{noline}{_txpr(800)}'
        f'<c:crossAx val="1001"/><c:crosses val="{"max" if bar_dir == "bar" else "autoZero"}"/><c:crossBetween val="between"/>'
        f'{major}</c:valAx>'
        f'<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr></c:plotArea>'
        f'{legend}<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
        f'<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>{_txpr(900)}</c:chartSpace>')


def _add_part(doc, spec: dict) -> str:
    pkg = doc.part.package
    n = getattr(doc, "_rg_chart_n", 0) + 1
    doc._rg_chart_n = n
    part = Part(PackURI(f"/word/charts/chart{n}.xml"), CT, chart_xml(spec).encode("utf-8"), pkg)
    return doc.part.relate_to(part, RT)


def add_to_paragraph(doc, paragraph, spec: dict, width_cm: float, height_cm: float) -> None:
    rid = _add_part(doc, spec)
    n = doc._rg_chart_n
    cx, cy = int(Cm(width_cm)), int(Cm(height_cm))
    xml = (f'<w:r xmlns:w="{NS_W}"><w:drawing><wp:inline xmlns:wp="{NS_WP}" distT="0" distB="0" distL="0" distR="0">'
           f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
           f'<wp:docPr id="{9000 + n}" name="차트 {n}"/><wp:cNvGraphicFramePr/>'
           f'<a:graphic xmlns:a="{NS_A}"><a:graphicData uri="{NS_C}">'
           f'<c:chart xmlns:c="{NS_C}" xmlns:r="{NS_R}" r:id="{rid}"/></a:graphicData></a:graphic>'
           f'</wp:inline></w:drawing></w:r>')
    paragraph._p.append(parse_xml(xml))


def add(doc, block: str, full_width_cm: float = 15.5) -> None:
    """```chart 블록 하나를 문서에 넣음. JSON이 깨졌으면 원문을 문단으로 남김."""
    try:
        spec = json.loads(block)
    except ValueError:
        doc.add_paragraph(f"[차트 데이터 오류] {block[:80]}")
        return
    row = spec.get("row")
    if row:
        t = doc.add_table(rows=1, cols=len(row))
        t.autofit = False
        w = full_width_cm / len(row)
        for cell, s in zip(t.rows[0].cells, row):
            cell.width = Cm(w)
            add_to_paragraph(doc, cell.paragraphs[0], s, s.get("width_cm", w - 0.3), s.get("height_cm", 5.0))
        doc.add_paragraph()
        return
    p = doc.add_paragraph()
    add_to_paragraph(doc, p, spec, spec.get("width_cm", full_width_cm), spec.get("height_cm", 6.0))
