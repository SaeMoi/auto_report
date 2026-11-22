"""보고서 디자인 값(글꼴·색·크기). 디자인 템플릿(1_결과보고서_템플릿_통합.docx, 2026-11-17)에서 가져옴.

색은 RRGGBB 16진수, 크기는 pt. 여기 값을 바꾸고 templates/make_reference.py를 다시 돌리면
본문 스타일(reference.docx)과 렌더러(docx.py)·표지(cover.py)가 같이 바뀜.
"""

FONT = "Noto Sans KR"   # 없으면 Word가 비슷한 글꼴로 대체함(무료: https://fonts.google.com/noto/specimen/Noto+Sans+KR)
MONO = "Consolas"

# 색
INK = "1C1C1C"        # 본문·제목
SUB = "55534E"        # 표 머리글·부제
MUTED = "8A877F"      # 머리말·쪽 번호·글머리표·캡션
RULE = "D9D6CE"       # 표 안쪽 가로선·머리말 밑줄
ACCENT = "2F5B63"     # 장 번호·표지 머리 문구
PAPER = "F5F4F0"      # 쪽 배경(미색). None이면 흰 바탕
IMG_BORDER, IMG_BORDER_PT = "1C1C1C", 0.5   # 본문 사진 테두리(배경과 경계 구분, 2026-11-19 팀 피드백). 색을 None으로 하면 테두리 없음
SUBTOTAL = "ECEAE4"   # 소계 행 바탕
CODE_BG, CODE_FG, CODE_DIM = "1C1C1C", "E9E7E1", "9B988F"

SEVERITY = {          # 위험도 글자색(■ 표시와 함께 씀)
    "critical": "9C3E39",
    "high": "B26A3C",
    "medium": "A88B35",
    "low": "5E7C5A",
    "info": "7B7F86",
}

OUTCOME = {           # 블루팀 탐지 결과 글자색(■ 표시와 함께 씀)
    "차단": "2F5B63",
    "탐지": "5E7C5A",
    "부분 탐지": "A88B35",
    "미탐": "9C3E39",
    "검증 무효": "7B7F86",
    # 모의해킹 단계 상태(2026-11-18): 확인은 진한 청록, 실패는 붉은색, 미시험은 옅은 회색
    "확인": "2F5B63",
    "실패": "9C3E39",
    "미시험": "B9B6AE",
}
CALLOUT_BG = "ECEAE4"  # 요점 상자 바탕
CHART_BEFORE, CHART_AFTER = "B9B6AE", "2F5B63"   # 차트: 개선 전 회색, 개선 후 청록

# 크기(pt)
BODY = 10
TABLE_HEAD = 9
TABLE_BODY = 9.5
H1, H2, H3, H4 = 17, 12.5, 11, 10.5
CODE = 9
CAPTION = 9
HEADER = 8.5
TRACKING = -0.2       # 자간(pt). 템플릿은 글자 사이를 살짝 좁힘

# 여백(cm). 템플릿: 위 2.6 / 아래 2.4 / 좌우 2.3
MARGIN_TOP, MARGIN_BOTTOM, MARGIN_SIDE = 2.6, 2.4, 2.3
CONTENT_WIDTH_CM = 21.0 - 2 * MARGIN_SIDE    # A4 본문 폭

SECURITY_LABEL = "대외비 · 팀 내부용"          # 머리말 오른쪽

COVER_STYLE = "minimal"   # 표지 모양: minimal(여백형) / band(왼쪽 띠형) / block(상단 블록형). render/cover.py 참고
