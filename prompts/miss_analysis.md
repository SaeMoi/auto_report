<!-- prompts/miss_analysis.md v0.1 — 작성(write): test_case.miss_analysis (블루 5-2 미탐 케이스 분석) -->
[작업: 작성 — 미탐 케이스 분석]
미탐 또는 3점 미만 케이스 하나에 대해 세 문항에 답함. text는 문자열 배열 3개(문항 순서대로)로 씀.
1. 어떤 텔레메트리(로그)가 생성됐어야 하는가: expected_observable과 기법 기준
2. 해당 로그를 수집하고 있었는가: log_sources의 collected·decoder 값으로만 판단
3. 해당 기법과 변형까지 탐지하려면 어떤 룰이 필요한가: 조건만 쓰고 룰 XML은 쓰지 않음
- log_sources에 없는 로그 소스는 「기준선에 없음」으로 씀
- 문체: ST-02a. 길이: {length}

[입력]
{context}
