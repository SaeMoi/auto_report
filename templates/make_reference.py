"""templates/reference.docx(글꼴·여백·머리말·바닥글·쪽 배경 원본)를 만듦.

디자인 값은 src/reportgen/render/theme.py에 있음(2026-11-17 디자인 템플릿 기준). 값을 고친 뒤 다시 실행:
  python templates/make_reference.py
Word에서 이 파일의 스타일(제목 1~4, 본문, 목록)을 고쳐 저장해도 이후 보고서에 반영됨.
본문 내용은 쓰지 않음(변환할 때 본문은 지우고 스타일만 씀). 표지는 render/cover.py가 따로 그림.
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

from reportgen.render import theme as T
from reportgen.render.docx import _set_font, _tracking

BULLET_NUM_ID = 90


def _style_font(st, size=None, bold=None, color=T.INK, tracking=T.TRACKING) -> None:
    st.font.name = T.FONT
    rpr = st.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for k in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(k), T.FONT)
    for k in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        fonts.attrib.pop(qn(k), None)
    if size:
        st.font.size = Pt(size)
    if bold is not None:
        st.font.bold = bold
    st.font.italic = False
    st.font.color.rgb = RGBColor.from_string(color)
    sp = rpr.find(qn("w:spacing"))
    if sp is None:
        sp = OxmlElement("w:spacing")
        rpr.append(sp)
    sp.set(qn("w:val"), str(int(round(tracking * 20))))


def _para_fmt(st, before, after, line, *, keep_next=False, page_break=False) -> None:
    pf = st.paragraph_format
    pf.space_before, pf.space_after, pf.line_spacing = Pt(before), Pt(after), line
    pf.keep_with_next = keep_next
    pf.page_break_before = page_break
    # 제목의 기본 테두리·색 띠 제거
    ppr = st.element.get_or_add_pPr()
    for tag in ("w:pBdr", "w:shd"):
        el = ppr.find(qn(tag))
        if el is not None:
            ppr.remove(el)


def _bullets(doc) -> None:
    """글머리표 ●(회색 작은 점) → ○ → ■. List Bullet 1~3 스타일에 연결."""
    numbering = doc.part.numbering_part.element
    lvls = ""
    for i, ch in enumerate("●○■●○■●●●"):
        lvls += (f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="{ch}"/>'
                 f'<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{567 + 425 * i}" w:hanging="283"/></w:pPr>'
                 f'<w:rPr><w:rFonts w:ascii="{T.FONT}" w:hAnsi="{T.FONT}"/><w:color w:val="{T.MUTED}"/>'
                 f'<w:sz w:val="14"/><w:szCs w:val="14"/></w:rPr></w:lvl>')
    absn = parse_xml(f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{BULLET_NUM_ID}">'
                     f'<w:multiLevelType w:val="hybridMultilevel"/>{lvls}</w:abstractNum>')
    num = parse_xml(f'<w:num {nsdecls("w")} w:numId="{BULLET_NUM_ID}"><w:abstractNumId w:val="{BULLET_NUM_ID}"/></w:num>')
    first_num = numbering.find(qn("w:num"))
    if first_num is not None:
        first_num.addprevious(absn)
    else:
        numbering.append(absn)
    numbering.append(num)
    for lvl, name in enumerate(("List Bullet", "List Bullet 2", "List Bullet 3")):
        st = doc.styles[name]
        _style_font(st, T.BODY)
        _para_fmt(st, 1, 1, 1.5)
        ppr = st.element.get_or_add_pPr()
        old = ppr.find(qn("w:numPr"))
        if old is not None:
            ppr.remove(old)
        ppr.insert(0, parse_xml(f'<w:numPr {nsdecls("w")}><w:ilvl w:val="{lvl}"/>'
                                f'<w:numId w:val="{BULLET_NUM_ID}"/></w:numPr>'))
        ind = ppr.find(qn("w:ind"))
        if ind is not None:
            ppr.remove(ind)


def _page_field(par) -> None:
    run = par.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    _set_font(run, T.FONT, T.HEADER)
    run.font.color.rgb = RGBColor.from_string(T.MUTED)


def _header(doc, section) -> None:
    hp = section.header.paragraphs[0]
    ppr = hp._p.get_or_add_pPr()
    ppr.append(parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="4" w:space="6" '
                         f'w:color="{T.RULE}"/></w:pBdr>'))
    for t in list(doc.styles["Header"].paragraph_format.tab_stops):   # 기본 가운데·오른쪽 탭 제거
        t._element.getparent().remove(t._element)
    hp.paragraph_format.tab_stops.add_tab_stop(Cm(T.CONTENT_WIDTH_CM), alignment=WD_TAB_ALIGNMENT.RIGHT)
    for text in ("보고서 제목", "\t" + T.SECURITY_LABEL):   # 첫 칸은 변환할 때 보고서 제목으로 바뀜
        r = hp.add_run(text)
        _set_font(r, T.FONT, T.HEADER)
        r.font.color.rgb = RGBColor.from_string(T.MUTED)
        _tracking(r, -0.15)
    fp = section.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _page_field(fp)


def _paper(doc) -> None:
    """쪽 배경색(미색). Word는 「배경 표시」 설정이 켜져야 보이므로 settings에도 씀."""
    if not T.PAPER:
        return
    doc.element.insert(0, parse_xml(f'<w:background {nsdecls("w")} w:color="{T.PAPER}"/>'))
    settings = doc.settings.element
    settings.insert(0, parse_xml(f'<w:displayBackgroundShape {nsdecls("w")}/>'))


def main() -> None:
    doc = Document()
    st = doc.styles
    _style_font(st["Normal"], T.BODY)
    _para_fmt(st["Normal"], 0, 6, 1.5)
    heads = {   # 스타일: (크기, 앞 간격, 뒤 간격, 줄 간격, 쪽 나눔)
        "Title": (30, 0, 18, 1.1, False),
        "Heading 1": (T.H1, 0, 12, 1.2, True),      # 장(1. 개요): 새 쪽에서 시작
        "Heading 2": (T.H2, 18, 6, 1.2, False),     # 절(1-1.)
        "Heading 3": (T.H3, 14, 5, 1.2, False),     # V-01. 같은 항목
        "Heading 4": (T.H4, 10, 4, 1.2, False),
    }
    for name, (size, before, after, line, brk) in heads.items():
        _style_font(st[name], size, True, tracking=-0.7 if name in ("Title", "Heading 1") else -0.35)
        _para_fmt(st[name], before, after, line, keep_next=True, page_break=brk)
    _bullets(doc)
    for s in doc.sections:
        s.page_width, s.page_height = Cm(21.0), Cm(29.7)
        s.left_margin = s.right_margin = Cm(T.MARGIN_SIDE)
        s.top_margin, s.bottom_margin = Cm(T.MARGIN_TOP), Cm(T.MARGIN_BOTTOM)
        s.header_distance = s.footer_distance = Cm(1.25)
        s.different_first_page_header_footer = True   # 표지에는 머리말·쪽 번호 없음
        _header(doc, s)
    _paper(doc)
    out = Path(__file__).resolve().parent / "reference.docx"
    doc.save(str(out))
    print(out)


if __name__ == "__main__":
    main()
