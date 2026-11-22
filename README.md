# reportgen — 보안 점검 보고서 자동화 도구

노션에 기록한 진단·모의해킹·탐지 검증 결과를 읽어 검사하고, AI가 문장을 다듬은 뒤, 수행 계획서·취약점 진단 보고서·모의해킹 보고서·블루팀 보고서를 Markdown·DOCX·PDF로 만듦.

- 사람이 내용을 씀. AI는 다듬기(polish)와 정해진 칸의 작성(write)만 함. 표·수치·ID는 프로그램이 만듦
- 기준 문서: `docs/spec/`의 양식 0·1·2, 보고서 자동화 규격서 v0.3, `docs/노션 DB 입력 규격.md`, `docs/REPORT_STYLE.md`

문서 순서: **1. 사전 세팅**(PC마다 처음 한 번) → **2. 실제 작업**(보고서를 만들 때마다, AI 앱에 한 줄 입력) → **3. 작동 방식** → **4~10. 상세 규칙**

## 1. 사전 세팅 (PC마다 처음 한 번)

### 1-1 준비물

| 준비물 | 용도 | 비고 |
| --- | --- | --- |
| Python 3.13 이상 | reportgen 실행 | macOS는 python.org 설치본 또는 Homebrew |
| Git | 코드 받기·갱신 | |
| LibreOffice | DOCX → PDF 변환 | 선택. PDF가 필요할 때만 |
| AI 앱 | 문장 작업·전체 진행 | Claude Code(데스크톱 앱 또는 CLI), Codex 중 하나 |

### 1-2 코드 받기

```bash
git clone https://github.com/SaeMoi/auto_report.git
cd auto_report
```

### 1-3 가상환경 만들기

macOS / Linux:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # 노션 API를 쓰면 ".[dev,notion]"
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

- `.venv`는 PC마다 새로 만들고 저장소에 올리지 않음
- 깨지면(`bad interpreter` 등, OneDrive 동기화 뒤 자주 생김) `.venv`를 지우고 위 명령으로 다시 만듦
- 저장소에 올리지 않는 것: `projects/`(실제 데이터), `backup_*/`, `.env`·`.env.*`(`.env.example` 제외), `.venv/`

### 1-4 설치 확인

```bash
.venv/bin/reportgen --help          # Windows: .venv\Scripts\reportgen --help
```

하위 명령(intake, prepare, ai, check, approve, render)이 보이면 됨.

### 1-5 선택 설정

- PDF: LibreOffice 경로를 `config/settings.yaml`의 `output.libreoffice`에 적음
- 노션 API(2안)를 쓸 때만 `.env`에 `NOTION_TOKEN=...`을 둠. 토큰은 저장소에 올리지 않음

### 1-6 AI 앱 연결

- AI 앱에서 「폴더 열기/연결」로 clone한 `auto_report` 폴더를 작업 폴더로 지정함
  - Claude Code 데스크톱 앱: 새 세션에서 폴더 선택 / CLI: 폴더에서 `claude` 실행
  - Codex: 폴더에서 `codex` 실행(또는 앱에서 폴더 선택)
- 작업 순서는 `CLAUDE.md`, 문장 작업 규칙은 `AGENTS.md`에 있음. 2-2의 한 줄로 AI가 이 파일들을 읽고 진행함
- **여기까지가 한 번만 하는 일임**

## 2. 실제 작업 (보고서를 만들 때마다)

### 2-1 노션 내보내기

1. 노션 「Report」 페이지 ⋯ → 내보내기 → 「Markdown & CSV」, 「하위 페이지 포함」
2. 받은 zip을 `projects/<프로젝트>/input/notion/red/`에 넣음(풀지 않아도 됨). 처음이면 `projects/<프로젝트>/` 폴더부터 만듦
3. 예전 zip은 빼 둠. 같은 폴더에 내보내기가 둘 이상이면 AI가 멈추고 물어봄

- 읽는 폴더는 `input/plan/`, `input/notion/red/`, `input/notion/blue/`, `input/notion/`이고 DB는 이름으로 알아봄. 나눠 받았다면 문서 정보·자산·목표는 `plan/`, R1~R7은 `notion/red/`, B1~B10은 `notion/blue/`에 둬도 됨

### 2-2 (자동) AI에게 맡기기

AI 앱에서 tools(`auto_report`) 폴더를 연 뒤 한 줄만 입력함:

```text
CLAUDE.md 읽고 작업해줘
```

- AI가 입력 검사부터 세 보고서(diag·pentest·blue) 초안까지 진행하고, 초안 경로와 확인할 것을 알려 줌. 입력 오류가 있으면 초안 전에 멈추고 고칠 노션 칸을 알려 줌
- 끝나면 AI가 다음 할 일(계획서, 최종본)을 물어봄. 그 밖의 요청은 평소 말로 하면 됨
- Codex도 같은 문구로 됨

### 2-2 (수동) 직접 명령어로 하기

`.venv`를 활성화한 뒤(macOS/Linux `source .venv/bin/activate`, Windows `.\.venv\Scripts\Activate.ps1`) 이 순서로 실행함:

```bash
reportgen prepare projects/<이름> -r diag     # ① 접수 검사 + AI 할 일 목록(work/diag/tasks.jsonl)
reportgen ai      projects/<이름> -r diag -a claude_cli   # ② 모델로 문장 작성(codex_cli, anthropic_api, openai_api도 됨). 에이전트가 results.jsonl을 직접 쓰면 생략
reportgen check   projects/<이름> -r diag     # ③ AI 결과 검사 + 검토 페이지(work/diag/review.md)
reportgen approve projects/<이름> -r diag <작업 ID> ...   # ④ 확인한 문장 잠금 (--all 가능)
reportgen render  projects/<이름> -r diag     # ⑤ output/diag_v<버전>.md/.docx/.pdf
```

- `-r`은 `plan`(수행 계획서), `diag`(취약점 진단 보고서), `pentest`(모의해킹 보고서), `blue`(블루팀 보고서), `all`(기본, diag·pentest·blue 세 권)
- `render --draft`는 검토 전 초안(미확정 AI 문장 포함). 입력 오류가 있으면 만들지 않음(`--force`로 무시). `--draft` 없이는 출력 전 검사를 통과해야 최종본이 나옴
- 옛 한 권짜리 `result`(결과 보고서)는 2026-11-22에 없앰. 노션 문서 정보(P1)에 진단·모의해킹 행이 없으면 「결과 보고서」 행을 대신 씀
- 블루팀 보고서는 ATT&CK Navigator 레이어(`attack_layer_before/after.json`)도 만듦

시연(가짜 데이터):

```bash
python samples/make_demo.py                     # 가짜 노션 내보내기 생성
reportgen prepare samples/demo -r diag
reportgen ai samples/demo -r diag -a fake     # 모델 없이 예시 문장
reportgen render samples/demo -r diag --draft
pytest -q
```

### 2-3 결과 확인

- `projects/<프로젝트>/output/`: 보고서 md·docx·pdf(초안·최종본)
- `projects/<프로젝트>/work/<보고서>/review.md`: 경고·`needs_review`·입력 문제를 한 장으로 봄
- 문장을 직접 고치려면 `work/<보고서>/locked.yaml`에 `작업 ID: 문장`으로 씀. 잠근 문장은 다시 돌려도 바뀌지 않음
- 특정 문장만 다시 쓰게 하려면 그대로 말하면 됨(예: `test1 V-03 개요 다시 써줘`)

### 2-4 코드 갱신

```bash
git pull
pip install -e ".[dev]"     # pyproject.toml이 바뀌었을 때만
```

## 3. 작동 방식

노션에 사람이 쓴 사실을 프로그램이 읽어 표·수치·ID를 만들고, AI는 정해진 칸의 문장만 쓰거나 다듬음. 사람이 검토·잠금한 뒤 Word·PDF로 냄.

```text
노션 내보내기 zip (projects/<이름>/input/)
   │ prepare ─────────────────────────────────────────────────────────
   ▼
intake    DB 이름으로 찾아 읽기 → 자동 마스킹 → 증거 번호 매기기 → 입력 검사
   ▼
build     canonical.json: 대표 건·위험도·CVSS 대조·통계, 자산·에이전트 대응, 블루→레드 연결·타임라인
   ▼
ai/tasks  AI 할 일 work/<보고서>/tasks.jsonl
   │ 에이전트(CLAUDE.md 읽고 작업해줘) 또는 reportgen ai ─────────────
   ▼
AI 작업   tasks.jsonl → results.jsonl  (사람이 쓴 사실은 바꾸지 않고 문장만 작성·다듬기)
   │ check ───────────────────────────────────────────────────────────
   ▼
check     AI 결과 규칙 검사 → 잠금 > AI 결과 순으로 합침 → report.json, review.md
   │ approve (사람이 정할 때) ─────────────────────────────────────────
   ▼
approve   확인한 문장을 locked.yaml에 잠금 (다시 돌려도 안 바뀜)
   │ render ──────────────────────────────────────────────────────────
   ▼
render    템플릿 → Markdown → 출력 전 검사 → DOCX → PDF (블루는 ATT&CK 레이어도)
```

| 단계 | 코드(`src/reportgen/`) | 읽는 것 | 만드는 것 |
| --- | --- | --- | --- |
| intake | `intake/notion_export.py`·`pages.py`·`mapping.py`, `intake/automask.py`, `intake/evidence.py`, `validate/rules.py` | `input/`의 노션 내보내기(zip은 프로젝트 밖 캐시에 풂), `config/settings.yaml`의 DB 이름 | 증거 `evidence/`, `build/evidence_map.json`, 입력 검사 `work/intake_report.md`, `work/<보고서>/intake_issues.json` |
| build | `build/merge.py`, `cvss.py`, `metrics.py`, `assets.py`, `link.py` | intake 결과 | `build/canonical.json`, `work/<보고서>/canonical.json` |
| AI 할 일 | `ai/tasks.py`, `ai/prompt_builder.py`, `prompts/` | canonical.json | `work/<보고서>/tasks.jsonl`, 사람이 채울 칸 `todo.json`, 빈 `results.jsonl`·`locked.yaml` |
| AI 작업 | 에이전트(`AGENTS.md`) 또는 `ai/runner.py` + `ai/adapters/` | `tasks.jsonl` | `results.jsonl` (같은 작업은 마지막 줄이 쓰임) |
| check | `ai/check.py`, `assemble.py`, `review.py` | canonical.json, `tasks.jsonl`, `results.jsonl`, `locked.yaml` | `work/<보고서>/report.json`, `review.md` |
| approve | `cli.py` | `results.jsonl` | `locked.yaml` |
| render | `render/markdown.py`(`templates/*.md.j2`), `validate/output.py`, `render/docx.py`, `render/pdf.py`, `render/attack_layer.py` | `report.json` | `output/<보고서>_v<버전>[_draft].md·docx·pdf`, `work/<보고서>/output_check.md` |

- `prepare` = intake + build + AI 할 일 생성(+ 첫 검토 페이지). `render`는 시작할 때 check를 한 번 더 돎
- 최종본(`--draft` 없음)은 입력 오류, 잠그지 않은 AI 문장(검토 필요·결과 없음), 출력 전 검사 오류 중 하나라도 있으면 만들지 않음

누가 무엇을 하나:

- **사람**: 노션에 사실(취약점·시나리오·탐지 결과·증거 그림) 입력, 스크린샷 속 비밀 값 가리기, 노션 내보내기, `review.md`·초안 검토, 어떤 문장을 잠글지와 최종본을 낼지 결정
- **프로그램**: 노션 읽기, 자동 마스킹, 증거 번호, 표·수치·ID·통계 계산, 입력·AI 결과·출력 전 검사, 문서 조립·변환
- **AI**: `tasks.jsonl`에 적힌 칸의 문장만 작성(write)·다듬기(polish). 수치·ID·경로는 바꾸지 않고, 모르면 `needs_review`로 돌려줌

## 4. 프로젝트 폴더

```text
projects/<이름>/
  project.yaml            (선택) config/settings.yaml 값을 덮어씀
  input/plan/             노션 내보내기: 문서 정보·자산·목표
  input/notion/red/       노션 내보내기: R1~R7
  input/notion/blue/      노션 내보내기: B1~B10
  evidence/  build/  work/<보고서>/  output/   ← 프로그램이 만듦
```

노션 내보내기는 「Markdown & CSV, 하위 페이지 포함」으로 받아 위 폴더에 풀어 둠(zip 그대로 둬도 됨).

## 5. 폴더 안내

| 폴더 | 내용 |
| --- | --- |
| `config/` | settings.yaml(노션 DB 이름, 증거 번호 대역, 출력), models.yaml(어댑터) |
| `reference/` | OWASP Top 10:2025 범주·점검 내용, PTEF 점수·공백 기준 |
| `schema/` | 정규 데이터(report.schema.json), AI 입출력(ai_output.schema.json) |
| `prompts/` | AI 지시문. `_common.md`에 공통 규칙과 REPORT_STYLE 규칙이 붙음 |
| `templates/` | 보고서 Markdown 템플릿(Jinja2), reference.docx(글꼴·스타일, 선택) |
| `src/reportgen/` | intake(노션 읽기) → build(계산) → validate(검사) → ai(할 일·검사) → assemble → render |
| `docs/` | 아키텍처, 문체 규칙, 노션 입력 규격, 팀원 안내 |

## 6. 입력 검사 기준 (완화 / 엄격)

- 기본은 완화 기준(`config/settings.yaml`의 `strict_input: false`). 보고서 초안이 먼저 나오게 함
  - 빈칸(날짜·작성자·조치 구분·자산 등), 진단 항목 판정 누락, 상세설명 소제목 누락은 오류가 아니라 경고로 알림. 보고서에는 `[확인 필요]`로 나옴
  - 「취약점 건」 상세설명에 소제목(위치·재현 과정 등)이 없으면 본문 전체를 「상세 설명」으로 받음
  - 「취약점」 본문(개요·악용 시나리오·조치방안)이 비어 있으면 같은 취약점의 대표 건 페이지에서 가져옴(취약점 설명 행, 「3. 악용 시나리오」, 「4. 조치방안」). 대표 건의 「마스킹 완료」가 켜져 있을 때만 가져옴
  - 그대로 오류로 남는 것: ID 누락·중복, 허용되지 않는 선택지, 마스킹 관련 오류
- 최종본 전에는 `strict_input: true`로 바꿔 규격대로 다시 검사함

## 7. 자동 마스킹

- 기본으로 켜져 있음(`auto_mask: true`). 노션에서 읽은 글·코드·표에서 JWT, Authorization 헤더, 세션·토큰 값, 비밀번호·키, AWS 식별자(인스턴스·AMI·액세스 키 등), 해시 값, 주민등록번호, 전화번호, 이메일을 규칙으로 가림. 모델을 쓰지 않고 이 컴퓨터 안에서 처리함
- 가린 값으로 AI 작업과 보고서를 만들므로 「마스킹 완료」 체크는 필요 없음. 무엇을 가렸는지는 검토 페이지 경고(규칙 「자동 마스킹」)에 나옴
- 스크린샷은 가리지 못함. 그림 속 토큰·계정·식별자는 사람이 가린 뒤 노션에 올림
- 자산 IP·출발지 IP는 보고서에 쓰는 값이라 가리지 않음. 문장에 평문으로 쓴 비밀번호처럼 규칙에 안 걸리는 값은 검토 때 확인함
- 규칙은 `src/reportgen/intake/automask.py`의 `RULES`. 끄려면 `auto_mask: false`(이때는 「마스킹 완료」를 체크한 페이지만 AI로 보냄)

## 8. 증거 그림 배치와 설명

- 상세설명은 노션에 쓴 순서 그대로 글과 그림을 번갈아 실음(그림 바로 앞뒤에 그 설명). 대표 건과 나머지 건 모두 같음. 그림을 본문에 싣지 않은 건(소제목 양식의 나머지 건, 낮음·정보 대표 건)만 부록 A로 감
- 증거 번호 목록은 연속 번호를 물결로 묶음(E-067, E-068, … E-072 → E-067~072)
- 그림 설명은 한 형식으로 맞춤: 「무엇을 했을 때 무엇이 보이는 화면」. AI 작업 `evidence.caption`이 모든 증거에 대해 만들어짐
  - AI는 그림 앞뒤 문단·노션 캡션·페이지 제목을 보고, `ai_read_images: true`(기본)면 그림 파일도 직접 봄(에이전트: 파일 경로, claude_cli: Read 허용, codex_cli: `-i`, API: 그림 첨부)
  - 노션 캡션이 파일 이름(image.png, Screenshot …png, 스크린샷 …)이면 버림
  - AI 결과가 없을 때는 「V-06-6 화면 (3/8)」 같은 기본 설명이 들어감
  - 그림이 모델로 나가므로 스크린샷 속 토큰·개인정보는 노션에 올리기 전에 가림. 보내고 싶지 않으면 `ai_read_images: false`
- 블루팀 보고서에 그림이 들어가는 곳은 `docs/노션 DB 입력 규격.md` 4-1-1 표(B1 구성도·Navigator·대시보드, B4 증거, B5 재검증 증거, B6 이미지)

## 9. 블루 보고서 지표 그래프·자산 표기

- 1-2 핵심 지표는 Word 차트(탐지율, 평균 점수, 탐지 결과, 점수별 케이스 수)로 들어감. 추가 설치 없음. Markdown에는 ```chart JSON으로 보임. Word에서 색·글꼴은 바꿀 수 있지만 「데이터 편집」은 안 됨(값은 노션을 고친 뒤 다시 만듦)
- 2-1의 「자산과 와주 에이전트 대응」 표가 기준. 자산 이름은 어디서나 「A-01 사용자 웹」, 에이전트는 P2 호스트와 B2 에이전트 칸(「001 (서버 이름)」)을 맞춰 정함. B2 로그 소스의 에이전트 서버가 그 자산의 서버와 다르면 출력 전 검사 O-13 오류

## 10. 출력 전 검사

- `render` 때 보고서 Markdown을 만든 뒤 `validate/output.py`가 점수·시각·건수 일치, 부록 A 룰 전문, 대기 문구(「[확인 필요]」「[AI 작업 대기]」)를 봄. 결과는 `work/<보고서>/output_check.md`
- 오류가 1건이라도 있으면 최종본을 만들지 않음. `--draft`면 초안은 만들고 목록만 남김
