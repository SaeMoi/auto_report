# Claude Code 안내

- 보고서 문장 작업 규칙은 `AGENTS.md`를 따름
- 코드 구조는 `docs/ARCHITECTURE.md`, 사용법은 `README.md`
- 시험: `python samples/make_demo.py && pytest -q`

## 작업 시작
사람이 「보고서 작업」 또는 「보고서 작업 <프로젝트>」라고만 입력하면 아래 순서로 진행함. `reportgen`은 `.venv/bin/reportgen`을 씀.
1. 대상: 프로젝트 이름이 없으면 `projects/` 아래 폴더를 봄. 하나면 그것으로, 여러 개면 목록을 보여 주고 물음
2. 환경: `.venv/bin/reportgen --help`가 안 되면 `python3.13 -m venv --upgrade .venv && .venv/bin/pip install -e ".[dev]"` 를 실행한 뒤 다시 확인
3. 입력: `projects/<이름>/input/` 아래(`plan/`, `notion/red/`, `notion/blue/`) 파일 이름만 봄(내용은 열지 않음). 한 폴더에 노션 내보내기 zip(또는 풀어 둔 폴더)이 둘 이상이면 옛 내보내기가 섞였을 수 있으니 멈추고 물음
4. `reportgen prepare projects/<이름>` (기본 `-r all` = diag·pentest·blue). 입력 오류가 있으면 여기서 멈추고, 오류마다 고칠 노션 DB·페이지·칸을 정리해 보고함. 경고는 보고서별 개수만 알림
5. 보고서별로 AGENTS.md 규칙대로 `work/<보고서>/tasks.jsonl`을 읽고 `results.jsonl`을 씀. 수행 계획서(`-r plan`)는 사람이 요청할 때만
6. `reportgen check projects/<이름>` 후 `work/<보고서>/review.md` 경고를 보고 고칠 결과는 다시 씀
7. `reportgen render projects/<이름> --draft`
8. 보고: 만든 초안 경로(`output/`), 입력 오류·needs_review 건수, 사람이 확인할 것
- 문장 잠금(`approve`)과 최종본(`render`에서 `--draft` 없이)은 사람이 요청할 때만 함
- `projects/` 데이터와 노션 내보내기는 고치지 않음. git commit·push 하지 않음
