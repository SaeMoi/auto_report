# 에이전트 작업 규칙 (Claude Code, Codex 등)

이 저장소에서 보고서 문장을 다듬는 에이전트가 지켜야 할 규칙임. 규격서 v0.3 5-8 「에이전트 실행 방식」을 따름.

## 할 일

1. 사람이 `reportgen prepare <프로젝트> -r <보고서>`를 실행한 뒤 요청함
2. `<프로젝트>/work/<보고서>/tasks.jsonl`을 한 줄씩 읽음. 각 줄의 `prompt`가 그 작업의 지시문 전체임
3. 작업마다 결과를 `<프로젝트>/work/<보고서>/results.jsonl`에 한 줄씩 덧붙임
   ```json
   {"task_id": "V-01:finding.overview", "text": "…", "cited_ids": ["V-01"], "changes": ["…"], "needs_review": false, "notes": ""}
   ```
   - `text`는 문자열. 지시문이 목록을 요구하면 문자열 배열
   - 확신이 없으면 `needs_review: true`와 `notes`에 이유를 씀
4. 끝나면 `reportgen check <프로젝트> -r <보고서>`를 실행하고 `review.md` ③·④의 경고를 확인함. 고친 결과는 같은 `task_id`로 다시 한 줄 덧붙임(마지막 줄이 쓰임)

## 금지

- `input/`, `evidence/`, `build/` 폴더와 증거 파일을 열지 않음. 읽는 파일은 `tasks.jsonl`, 쓰는 파일은 `results.jsonl`뿐임
  - 예외: 그림 설명 작업(`evidence.caption`)에 `image` 경로가 있으면 그 그림 파일 하나만 열어 화면을 확인함
- 지시문에 없는 사실(수치, 시각, IP, 경로, 계정, ID)을 만들지 않음. 빈 칸은 채우지 않고 `needs_review`로 돌려줌
- `locked.yaml`을 고치지 않음(사람이 확정한 문장)
- 다듬기(polish)에서 원문의 ID·URL·경로·코드·숫자를 바꾸거나 빼지 않음(R-27)
- 보고서에 인스턴스 ID, AMI ID, 키 페어 이름, IAM 이름, 접속 스크립트 경로를 쓰지 않음

## 그림 설명(evidence.caption)

- 모든 증거에 같은 형식으로 씀: 「무엇을 했을 때 무엇이 보이는 화면」(요청·응답은 「~ 요청·응답」, 로그는 「~ 로그」), 40자 이내 명사구
- 파일 이름·날짜·「스크린샷」을 쓰지 않음. 그림 속 토큰·비밀번호·개인정보 값은 옮겨 적지 않음
- 그림을 볼 수 없고 앞뒤 문단으로도 알 수 없으면 「[확인 필요]」, `needs_review: true`

## 문체

- `docs/REPORT_STYLE.md`를 따름. 지시문 앞부분에 같은 규칙이 붙어 있음
- 문장 끝은 「~함·~됨·~임」. 설명 칸(ST-02a)은 지시문이 허용하는 범위에서 서술형 가능
