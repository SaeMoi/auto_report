# reportgen 구조

## 흐름

```text
노션 내보내기(1안) / 노션 API(2안) / canonical.json(시연)
        │ intake/notion_export.py, notion_api.py → pages.py(Page·Block)
        ▼
intake/mapping.py        노션 속성·본문 → 정규 데이터(규격서 3장). 문서 정보(P1)는 보고서 종류에 맞는 행을 고름
intake/evidence.py       본문 그림·코드 → 증거 E-NNN (레드 001~, 블루 500~, build/evidence_map.json으로 번호 고정)
build/merge.py           대표 건·위험도·건수·역참조·목표 시간·탐지 소요·타임라인 계산
validate/rules.py        R-01~R-26 접수 검사 → work/intake_report.md
        │  build/canonical.json
        ▼
ai/tasks.py              AI 할 일(work/<보고서>/tasks.jsonl). 마스킹 완료가 아닌 값은 넣지 않음. 빈 칸은 사람 몫(todo.json)
        │  (에이전트 또는 ai/runner.py + adapters/*)
        ▼  work/<보고서>/results.jsonl
ai/check.py              R-14 문체, R-15 인용 ID, R-17 길이, R-27 다듬기 보존, R-18 AI 검토 요청
assemble.py              잠금(locked.yaml) > AI 결과 > 「[AI 작업 대기]」 순으로 합침 → work/<보고서>/report.json
review.py                검토 페이지 work/<보고서>/review.md (① 입력 오류 ② 사람이 채울 사실 ③ AI 문장 ④ 경고)
        ▼
render/markdown.py       templates/<보고서>.md.j2 (Jinja2) → output/*.md
render/docx.py           Markdown → DOCX (python-docx, templates/reference.docx가 있으면 그 스타일)
render/pdf.py            DOCX → PDF (LibreOffice)
render/attack_layer.py   블루팀 ATT&CK Navigator 레이어
```

## 설계 판단

- **렌더링: Jinja2 Markdown → 자체 DOCX 변환**. docxtpl(Word 템플릿에 태그 삽입)은 표 행 반복·조건 장이 많아 템플릿 관리가 어렵고, 양식 0·1·2가 Markdown으로 관리되므로 같은 형식으로 템플릿을 둠. Markdown 결과물은 검토·비교용으로도 남김. 글꼴·여백은 `templates/reference.docx`로 바꿈
- **에이전트 기본 경로**. 모델 API 키 없이 Claude Code 등 에이전트가 tasks.jsonl만 읽고 results.jsonl만 쓰게 함. 같은 지시문을 `reportgen ai -a <어댑터>`로 프로그램이 직접 보낼 수도 있음
- **잠금 우선**. 사람이 확정한 문장(locked.yaml)은 AI를 다시 돌려도 바뀌지 않음
- **확정 전 발행 차단**. `render`는 미확정 AI 문장이 있으면 멈춤. 초안은 `--draft`
- **문서 정보(P1)는 보고서마다 한 행**. 버전 규칙(R-19 블루팀 0.5·1.0)이 보고서마다 다르기 때문

## 작업 폴더

| 파일 | 만드는 곳 | 내용 |
| --- | --- | --- |
| build/canonical.json | prepare | 정규 데이터(계산 포함) |
| build/evidence_map.json | prepare | 증거 해시 → 번호(다시 실행해도 번호 유지) |
| work/intake_report.md | prepare | 접수 검사 결과 |
| work/<보고서>/tasks.jsonl | prepare | AI 할 일 |
| work/<보고서>/todo.json | prepare | 사람이 채울 칸 |
| work/<보고서>/results.jsonl | 에이전트·ai | AI 결과(덧붙이기, 같은 작업은 마지막 줄) |
| work/<보고서>/locked.yaml | 사람·approve | 확정 문장 |
| work/<보고서>/report.json | check | 보고서용 데이터 |
| work/<보고서>/review.md | check | 검토 페이지 |
