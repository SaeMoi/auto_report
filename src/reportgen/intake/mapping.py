"""Page 목록(노션) → canonical 데이터(규격서 v0.3 3장).

속성 이름·선택지·본문 제목은 docs/노션 DB 입력 규격.md 를 따름. 이 파일의 표(MAP)만 고치면 이름 변경에 대응함.
읽는 중 발견한 문제는 issues 목록에 쌓아 intake_report.md로 돌려줌(사람이 노션에서 고침).
"""
from __future__ import annotations

import re
import textwrap
from collections import defaultdict

from .pages import (Block, Page, all_tables, blocks_to_md, first_code, first_table, heading_level, kv_table, list_items,
                    split_ids, text_of)

# ── 선택지 → 열거형 ────────────────────────────────────────────
# 「결과 보고서」는 옛 한 권짜리(2026-11-22 보고서 종류에서 없앰). 기존 노션 데이터 호환을 위해 선택지로만 남김:
# 그 행은 diag·pentest가 대신 쓰고(REPORT_FALLBACK), report_type은 intake/check.py에서 만들 보고서로 덮어씀
REPORT_TYPE = {"수행 계획서": "plan", "결과 보고서": "result", "블루팀 보고서": "blue",
               "취약점 진단 보고서": "diag", "모의해킹 보고서": "pentest"}
# 2026-11-18 결과 보고서를 진단(diag)·모의해킹(pentest) 두 권으로 나눔. 노션에 그 종류의 문서 정보 행이 없으면 결과 보고서 행을 씀
REPORT_FALLBACK = {"diag": "result", "pentest": "result"}
ZONE = {"외부(DMZ)": "external_dmz", "관리·내부": "internal_admin"}
CRIT = {"상": "high", "중": "mid", "하": "low"}
SCOPE = {"범위 내": "in_scope", "범위 밖 발견": "out_of_scope"}
OBJ_TYPE = {"1차": "primary", "2차": "secondary"}
OBJ_STATUS = {"달성": "achieved", "부분 달성": "partial", "미달성": "not_achieved"}
SEVERITY = {"info": "info", "low": "low", "medium": "medium", "high": "high", "critical": "critical"}
DISCOVERY = {"수동": "manual", "자동 도구": "auto"}
STATUS = {"미조치": "open", "조치 완료": "fixed", "부분 조치": "partial", "재검증 완료": "verified"}
CLASSIFICATION = {"확정": "confirmed", "확인 필요": "needs_check"}
FIX_PRIORITY = {"즉시": "immediate", "단기": "short", "중기": "mid"}
CHECK = {"양호": "good", "취약": "vulnerable", "해당 없음": "na"}
START = {"외부 공격자": "external", "회원 계정": "member", "침해 가정": "assumed_breach"}
STEP_RESULT = {"확인": "success", "성공": "success", "실패": "failed", "미시험": "untested"}   # 성공은 옛 선택지
TIME_BASIS = {"로그": "log", "화면": "screen", "추정": "estimate", "확인 필요": "unknown"}
PATCH_TYPE = {"코드 수정": "code", "설정 변경": "config", "기능 제거": "removal", "임시 차단": "temporary"}
PATCH_SCOPE = {"해당 건만": "instance", "같은 취약점 전체": "finding"}
CHAIN = {"체인 차단됨": True, "여전히 가능": False, "해당 없음": None}
TEST_SOURCE = {"시나리오 단계": "scenario_step", "취약점 건": "finding_instance", "ATT&CK 모사": "attack_emulation"}
TEST_STATUS = {"계획": "planned", "실행 완료": "executed"}
OUTCOME = {"차단": "blocked", "탐지": "detected", "미탐": "not_detected", "검증 무효": "invalid"}
GAP = {"가시성": "visibility", "탐지 로직": "detection_logic", "경보 억제": "alert_suppression",
       "프로세스": "process", "적시성": "timeliness", "없음": "none", "검증 무효": "invalid"}
TRIAGE = {"정탐": "true_positive", "오탐": "false_positive"}
DECODER = {"기본": "builtin", "커스텀": "custom", "없음": "none"}
MODULE = {"파일 무결성 감시": "fim", "보안 설정 평가": "sca", "취약점 탐지": "vulnerability_detection",
          "Active Response": "active_response"}
CLOUD = {"보안그룹 변경": "security_group", "IAM 변경": "iam", "콘솔 로그인": "console_login"}
TASK_STATUS = {"미착수": "todo", "진행": "in_progress", "완료": "done"}
VERIFY_MODE = {"블라인드": "blind", "협업형 퍼플팀": "collaborative"}
YES = {"예", "켬", "yes", "true", "참", "o", "허용"}

METHOD_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)")
CVSS_SCORE_RE = re.compile(r"\(?\s*(\d+(?:\.\d)?)\s*\)?")


class Mapper:
    def __init__(self, pages: list[Page], report: str | None = None, lenient: bool = True):
        self.report = report
        self.lenient = lenient    # 완화 기준: ID가 아닌 빈칸은 오류 대신 경고
        self.by_db: dict[str, list[Page]] = defaultdict(list)
        for p in pages:
            self.by_db[p.db].append(p)
        self.issues: list[dict] = []
        self.evidence_raw: list[dict] = []    # 번호 발급 전 증거 후보

    # ── 문제 기록 ──
    def err(self, where: str, msg: str, rule: str = "R-01") -> None:
        self.issues.append({"level": "error", "rule": rule, "where": where, "msg": msg})

    def empty(self, where: str, prop: str) -> None:
        """빈칸 기록. 완화 기준에서는 ID 칸만 오류로 남김."""
        msg = f"「{prop}」이 비어 있음"
        if self.lenient and not prop.endswith("ID") and prop != "문서 종류":
            self.warn(where, msg + "(보고서에 [확인 필요]로 나옴)", "R-01")
        else:
            self.err(where, msg)

    def warn(self, where: str, msg: str, rule: str = "") -> None:
        self.issues.append({"level": "warning", "rule": rule, "where": where, "msg": msg})

    def enum(self, page: Page, prop: str, table: dict, where: str, required: bool = True, default=None):
        raw = page.prop(prop)
        if not raw:
            if required and default is None:   # 기본값이 있으면 비워도 됨
                self.empty(where, prop)
            return default
        key = raw if raw in table else raw.lower() if raw.lower() in table else None
        if key is None:
            self.err(where, f"「{prop}」 값 「{raw}」은 허용 선택지가 아님({', '.join(map(str, table))})", "R-02")
            return default
        return table[key]

    def need(self, page: Page, prop: str, where: str) -> str:
        v = page.prop(prop)
        if not v:
            self.empty(where, prop)
        return v

    # ── 증거 후보 수집 ──
    def collect_evidence(self, owner_id: str, page: Page, blocks: list[Block], masked: bool, team: str,
                         code_as_evidence: bool = True) -> dict[int, str]:
        """증거 후보를 쌓고, 블록 위치 → 증거 참조 키(ref)를 돌려줌(본문 흐름에서 그림 자리를 찾는 데 씀)."""
        refs: dict[int, str] = {}
        for i, b in enumerate(blocks):
            if b.type == "image":
                nxt = blocks[i + 1] if i + 1 < len(blocks) else None
                hint = nxt.text.strip() if nxt is not None and nxt.type == "paragraph" else ""
                prev = blocks[i - 1].text.strip() if i and blocks[i - 1].type in ("paragraph", "bullet", "numbered") else ""
                ref = f"{owner_id}#{len(self.evidence_raw)}"
                self.evidence_raw.append({"owner_id": owner_id, "kind": "screenshot", "path": b.path,
                                          "caption": clean_caption(b.text), "masked": masked, "team": team,
                                          "source": page.source, "ref": ref,
                                          "near": {"before": prev[:300], "after": hint[:300]}})
                refs[i] = ref
            elif b.type == "code" and code_as_evidence:
                ref = f"{owner_id}#{len(self.evidence_raw)}"
                self.evidence_raw.append({"owner_id": owner_id, "kind": code_kind(b.text), "content": b.text,
                                          "lang": b.lang, "caption": "", "masked": masked, "team": team,
                                          "source": page.source, "ref": ref})
                refs[i] = ref
        return refs

    def collect_flow(self, owner_id: str, page: Page, blocks: list[Block], masked: bool, team: str,
                     code_as_evidence: bool = True) -> list[dict]:
        """증거를 모으면서 본문 흐름(글·그림·코드를 쓴 순서대로)을 만듦. 피드백: 사진과 설명을 번갈아 서술."""
        refs = self.collect_evidence(owner_id, page, blocks, masked, team, code_as_evidence)
        return build_flow(blocks, refs)

    # ── 공통(수행 계획) ──
    def project(self) -> dict:
        ps = self.by_db.get("P1", [])
        if not ps:
            self.err("P1 문서 정보", "문서 정보 페이지가 없음")
            return {}
        # 문서 정보는 문서 종류마다 한 행. 만들 보고서와 같은 종류의 행을 고르고, 없으면 첫 행을 씀
        want = {v: k for k, v in REPORT_TYPE.items()}.get(self.report or "")
        p = next((x for x in ps if x.prop("문서 종류") == want), None)
        if p is None and self.report in REPORT_FALLBACK:
            alt = {v: k for k, v in REPORT_TYPE.items()}[REPORT_FALLBACK[self.report]]
            p = next((x for x in ps if x.prop("문서 종류") == alt), None)
            if p is not None:
                self.warn(f"P1 {p.title}", f"「{want}」 문서 정보 행이 없어 「{alt}」 행을 씀(표지·개정 이력이 같게 나옴)")
                self.title_override = re.sub(r"(취약점 진단 및 모의해킹 )?결과 보고서", want, p.title) \
                    if "결과 보고서" in p.title else want
        p = p or ps[0]
        w = f"P1 {p.title}"
        proj = {
            "name": p.prop("프로젝트", "sesacedu.store 보안 점검 프로젝트"),
            "title": getattr(self, "title_override", "") or p.title,
            "report_type": self.enum(p, "문서 종류", REPORT_TYPE, w),
            "version": self.need(p, "버전", w),
            "period": {"start": self.need(p, "수행 시작일", w)[:10], "end": self.need(p, "수행 종료일", w)[:10]},
            "security_level": p.prop("보안 등급", "대외비 (팀 내부용)"),
            "reviewers": split_names(p.prop("검토자")),
            "standards": {"owasp": "2025", "cvss": "3.1"},
        }
        if p.prop("진단 기간"):
            proj["diag_period_text"] = p.prop("진단 기간")
        if p.prop("모의해킹 기간"):
            proj["pentest_period_text"] = p.prop("모의해킹 기간")
        proj["authors"] = [
            {"name": r.get("이름", ""), "role": r.get("역할", ""), "chapters": r.get("담당 장", ""),
             "contact": r.get("연락처", ""), "area": r.get("담당 영역", "")}
            for r in first_table(p.section("작성자")) if r.get("이름")]
        if not proj["authors"]:
            (self.warn if self.lenient else self.err)(w, "본문 「작성자」 표가 비어 있음", "R-01")
        proj["revisions"] = [
            {"version": r.get("버전", ""), "date": r.get("날짜", ""), "author": r.get("작성자", ""),
             "changes": r.get("변경 내용", "")} for r in first_table(p.section("개정 이력"))]
        memo = text_of(p.section("요약 메모"))
        if memo:
            proj["summary_memo"] = memo
        purpose = text_of(p.section("진단 목적"))
        if purpose:
            proj["purpose"] = purpose
        proj["conditions"] = [
            {"phase": r.get("단계", ""), "source_ip": r.get("출발지 IP", ""),
             "ip_allowed": r.get("IP 허용", "").strip() in ("허용", "예"),
             "active_response": r.get("Active Response", "").strip() in ("켬", "예"),
             "start_condition": r.get("시작 조건", "")} for r in first_table(p.section("수행 조건"))]
        proj["good_practices"] = [
            {"item": r.get("항목", ""), "effect": r.get("효과", ""), "cited_ids": split_ids(r.get("근거 ID", ""))}
            for r in first_table(p.section("잘 된 보안 사항 메모"))]
        tools = list_items(p.section("사용 도구"))
        if tools:
            proj["tools"] = tools
        accounts = first_table(p.section("테스트 계정"))
        if accounts:
            # 노션은 메일 주소를 자동으로 메일 링크로 바꾸고 「[a@x.com](mailto:a@x.com)」로 내보냄. 메일(ID) 글자만 남김(2026-11-22)
            def _plain_id(v: str) -> str:
                return re.sub(r"\[([^\]]*)\]\(mailto:[^)]*\)", r"\1", v or "").strip()
            proj["test_accounts"] = [{"name": _plain_id(r.get("계정", "")), "role": (r.get("권한", "") or "").strip()}
                                     for r in accounts]
        # 수행 계획서 전용: 사람이 쓴 장을 그대로 옮김(표·목록 형식 유지)
        plan = {}
        for key in ("수행 개요", "범위", "수행 규칙", "디컨플릭션", "비상 연락", "네트워크 구성", "승인"):
            if p.has_section(key):
                plan[key] = blocks_to_md(p.section(key))
        if plan:
            proj["plan_sections"] = plan
        # 인프라(네트워크) 구성도: 본문 「네트워크 구성」의 그림. 고른 행에 없으면 다른 문서 정보 행에서 찾음
        src = next((x for x in [p] + ps if any(b.type == "image" for b in x.section("네트워크 구성"))), None)
        if src:
            self.collect_evidence("P1", src, src.section("네트워크 구성"), True, "red", code_as_evidence=False)
        sched = first_table(p.section("일정"))
        if sched:
            proj["schedule"] = [{"phase": r.get("단계", ""), "period": r.get("기간", ""), "content": r.get("내용", "")}
                                for r in sched]
        return proj

    def assets(self) -> list[dict]:
        out = []
        for p in self.by_db.get("P2", []):
            aid = p.prop("자산 ID")
            w = f"P2 {aid or p.title}"
            ports = [int(x) for x in re.findall(r"\d+", p.prop("열린 포트"))]
            out.append({
                "asset_id": self.need(p, "자산 ID", w), "name": p.title, "host": p.prop("호스트"),
                "ip": {"public": p.prop("공인 IP"), "private": p.prop("사설 IP")},
                "zone": self.enum(p, "구역", ZONE, w), "role": self.need(p, "역할", w),
                "stack": p.prop("기술 스택"), "open_ports": ports,
                "access_control": self.need(p, "접근 통제", w),
                "criticality": self.enum(p, "중요도", CRIT, w, required=False),
                "wazuh_agent": p.prop("와주 에이전트") or None,
                "start_condition": p.prop("시작 조건"),
                "scope": self.enum(p, "범위", SCOPE, w, default="in_scope"),
            })
        return sorted(out, key=lambda a: a["asset_id"] or "")

    def objectives(self) -> list[dict]:
        out = []
        for p in self.by_db.get("P3", []):
            w = f"P3 {p.prop('목표 ID') or p.title}"
            out.append({
                "objective_id": self.need(p, "목표 ID", w), "title": p.title,
                "type": self.enum(p, "구분", OBJ_TYPE, w),
                "success_criteria": self.need(p, "달성 판단 기준", w),
                "status": self.enum(p, "결과", OBJ_STATUS, w, required=False),
                "scenario_ids": p.ids("시나리오"),
            })
        return sorted(out, key=lambda o: o["objective_id"] or "")

    # ── 레드팀 ──
    def findings(self) -> list[dict]:
        out = []
        for p in self.by_db.get("R2", []):
            fid = p.prop("취약점 ID")
            w = f"R2 {fid or p.title}"
            otype = p.prop("취약점 유형")
            code = otype[:3] if re.match(r"^A(0[1-9]|10)\b", otype) else None
            if not code:
                self.err(w, f"「취약점 유형」 값 「{otype}」이 OWASP A01~A10 형식이 아님", "R-13")
            cwes = [c.upper().replace(" ", "") for c in re.findall(r"CWE\s*-\s*\d+", p.prop("CWE"), re.I)]
            if not cwes:
                self.err(w, "「CWE」가 비어 있거나 CWE-번호 형식이 아님", "R-13")
            steps = list_items(p.section("조치방안"))
            overview = text_of(p.section("개요"))
            exploit = text_of(p.section("악용 시나리오"))
            # 완화 기준: R2 본문이 비어 있으면 같은 취약점의 대표 건 페이지(팀 기존 양식)에서 가져옴
            src = self._rep_page(fid)
            if src is not None and src.flag("마스킹 완료"):
                took = []
                if not overview:
                    ov = kv_table(src.section("1. 취약점 개요")) or kv_table(src.section("취약점 개요"))
                    overview = ov.get("취약점 설명", "")
                    took += ["개요"] if overview else []
                if not exploit:
                    exploit = text_of(src.section("악용 시나리오"))
                    took += ["악용 시나리오"] if exploit else []
                if not steps:
                    sec = src.section("조치방안")
                    steps = list_items(sec) or [x.strip() for x in first_code(sec).splitlines() if x.strip()]
                    took += ["조치방안"] if steps else []
                if took:
                    self.warn(w, f"R2 본문이 비어 대표 건 페이지에서 가져옴: {', '.join(took)}", "R-07")
            out.append({
                "finding_id": self.need(p, "취약점 ID", w), "title": p.title, "owasp_2025": code,
                "cwe": cwes,
                "classification": self.enum(p, "분류 확정", CLASSIFICATION, w, default="needs_check"),
                "fix_priority": self.enum(p, "조치 구분", FIX_PRIORITY, w, required=False),
                "root_cause": p.prop("근본 원인"),
                "references": split_list(p.prop("참고 링크")),
                "code_reviewed": p.flag("코드 검토 완료"),
                "overview": overview,
                "exploit_scenario": exploit,
                "remediation": {
                    "cause": text_of(p.section("원인")),
                    "steps": steps,
                    "code_before": first_code(p.section("취약한 코드")),
                    "code_after": first_code(p.section("수정한 코드")),
                    "code_lang": next((b.lang for b in p.section("수정한 코드") if b.type == "code"), ""),
                    "config_change": text_of(p.section("설정 변경")),
                },
                "masked": True,
            })
        return sorted(out, key=lambda f: f["finding_id"] or "")

    def _rep_page(self, fid: str) -> Page | None:
        """취약점 ID가 fid인 건 중 대표 건(-1) 페이지. 없으면 첫 건."""
        its = [p for p in self.by_db.get("R1", []) if p.prop("취약점 ID") == fid and fid]
        its.sort(key=lambda p: id_key(p.prop("건 ID") or "V-99-99"))
        return next((p for p in its if p.prop("건 ID").endswith("-1")), its[0] if its else None)

    def instances(self) -> list[dict]:
        out = []
        for p in self.by_db.get("R1", []):
            iid = p.prop("건 ID")
            w = f"R1 {iid or p.title}"
            access = self.need(p, "접근경로", w)
            loc = parse_location(access)
            ov = kv_table(p.section("1. 취약점 개요"))
            impact = ov.get("영향도(CVSS 3.1)", "") or ov.get("영향도 (CVSS 3.1)", "")
            score = None
            m = re.search(r"(\d+(?:\.\d)?)", impact)
            if m:
                score = float(m.group(1))
            vector = re.sub(r"[*`\s]", "", ov.get("CVSS Vector", ""))
            detail = p.section("2. 취약점 상세설명")
            masked = p.flag("마스킹 완료")
            inst = {
                "instance_id": self.need(p, "건 ID", w), "finding_id": self.need(p, "취약점 ID", w),
                "title": p.title,
                "asset_id": self.need(p, "자산", w), "location": loc,
                "path_found": ov.get("발견 경로", ""),
                "target_desc": ov.get("점검대상", ""),
                "cvss": {"version": "3.1", "vector": vector, "score": score},
                "severity": self.enum(p, "위험도", SEVERITY, w),
                "discovery": self.enum(p, "발견 방법", DISCOVERY, w, required=False, default="manual"),
                "intentional": p.flag("의도적 취약점"),
                "status": self.enum(p, "조치 상태", STATUS, w, default="open"),
                "step_ids": p.ids("시나리오 단계"), "test_ids": p.ids("탐지 검증"),
                "masked": masked,
            }
            if iid.endswith("-1"):
                res = p.section("결과", within=detail)
                inst["poc"] = {
                    "location": text_of(p.section("위치", within=detail)),
                    "steps": list_items(p.section("재현 과정", within=detail)),
                    "request": first_code(p.section("공격 요청", within=detail)),
                    "explanation": text_of(p.section("공격 설명", within=detail)),
                    "response": first_code(res),
                    "result_facts": _facts(res),
                }
                if not inst["poc"]["request"] and "해당 없음" in text_of(p.section("공격 요청", within=detail)):
                    inst["poc"]["request"] = "해당 없음"
                poc = inst["poc"]
                if not (poc["location"] or poc["steps"] or poc["explanation"] or res):
                    # 완화 기준: 소제목 없이 자유롭게 쓴 상세설명을 통째로 받음
                    poc["freeform"] = True
                    poc["location"] = access
                    poc["explanation"] = _free_text(detail)
                    poc["request"] = first_code(detail)
                    # 글·그림·코드를 쓴 순서대로 보여 주기 위한 흐름
                    inst["flow"] = self.collect_flow(iid, p, detail, masked, "red", code_as_evidence=False)
                else:
                    self.collect_evidence(iid, p, res, masked, "red", code_as_evidence=False)
                    # 2026-11-21: 「공격 요청」에 요청 원문 대신 패킷 화면을 둔 경우 → 그 그림을 요청 자리에
                    req_imgs = [b for b in p.section("공격 요청", within=detail) if b.type == "image"]
                    if req_imgs and not poc["request"]:
                        poc["request_refs"] = list(self.collect_evidence(iid, p, req_imgs, masked, "red").values())
                    else:
                        req_imgs = []
                    # 결과 외 위치의 스크린샷도 증거로
                    others = [b for b in detail if b.type == "image" and b not in res and b not in req_imgs]
                    self.collect_evidence(iid, p, others, masked, "red")
            else:
                inst["diff"] = text_of(p.section("대표 건과 다른 점", within=detail))
                if not inst["diff"]:   # 완화 기준: 소제목이 없으면 상세설명 전체
                    inst["diff"] = _free_text(detail)
                    inst["freeform"] = bool(inst["diff"])
                inst["flow"] = self.collect_flow(iid, p, detail, masked, "red")
            out.append(inst)
        return sorted(out, key=lambda i: id_key(i["instance_id"]))

    def check_items(self) -> list[dict]:
        out = []
        for p in self.by_db.get("R3", []):
            code = p.prop("항목 코드")
            w = f"R3 {code or p.title}"
            results = []
            for k, v in p.props.items():
                m = re.match(r"판정:\s*(A-\d{2})", k)
                if m and v.strip():
                    if v.strip() not in CHECK:
                        self.err(w, f"「{k}」 값 「{v}」은 허용 선택지가 아님", "R-02")
                        continue
                    results.append({"asset_id": m.group(1), "result": CHECK[v.strip()]})
            checked = [x for x in split_list(p.prop("점검 취약점"), sep=r"[,\n]")]
            item = {"code": code, "name": p.title, "results": sorted(results, key=lambda r: r["asset_id"]),
                    "note": p.prop("비고")}
            if checked:
                item["checked_items"] = [{"title": t} for t in checked]
            out.append(item)
        return sorted(out, key=lambda c: c["code"] or "")

    def scenarios(self) -> list[dict]:
        steps_by_s: dict[str, list[dict]] = defaultdict(list)
        for p in self.by_db.get("R5", []):
            sid = p.prop("단계 ID")
            w = f"R5 {sid or p.title}"
            masked = p.flag("마스킹 완료")
            actions_blocks = merge_image_captions(p.section("수행 내용"))
            actions = []
            for b in actions_blocks:
                if b.type in ("bullet", "numbered", "paragraph") and b.text.strip() and not heading_level(b):
                    actions.append(b.text.strip())
                elif b.type == "code":
                    actions.append("```\n" + b.text + "\n```")
            status = self.enum(p, "결과", STEP_RESULT, w)
            untested = status == "untested"
            # 미시험 단계는 시각·IP가 없어도 됨
            need = (lambda prop: p.prop(prop)) if untested else (lambda prop: self.need(p, prop, w))
            start_raw, end_raw = need("시작 시각(초)"), p.prop("종료 시각(초)")
            step = {
                "step_id": self.need(p, "단계 ID", w), "name": p.title,
                "purpose": self.need(p, "목적", w),
                "start_at": to_kst(start_raw), "end_at": to_kst(end_raw) or to_kst(start_raw),
                "time_basis": TIME_BASIS.get(p.prop("시각 근거"), "") if p.prop("시각 근거") else "",
                "source_ip": need("출발지 IP"), "asset_id": self.need(p, "대상 자산", w),
                "instance_ids": p.ids("사용 취약점"), "attack_technique": need("ATT&CK 기법"),
                "tactic": p.prop("전술"),
                "actions": actions,
                "flow": self.collect_flow(sid, p, actions_blocks, masked, "red"),
                "rationale": text_of(p.section("판단 근거")),
                "result": {"status": status, "gained": p.prop("획득한 것"), "blocked_reason": p.prop("막힌 이유")},
                "target_impact": p.prop("대상에 남긴 영향"),
                "expected_artifacts": list_items(p.section("남아야 하는 로그")),
                "detection_idea": text_of(p.section("탐지 기회")),
                "test_ids": p.ids("탐지 검증"),
                "masked": masked,
            }
            if start_raw and not step["start_at"]:
                self.warn(w, f"「시작 시각(초)」 값 「{start_raw}」을 읽지 못함(YYYY-MM-DD HH:MM 형식으로)", "R-16")
            if not actions and not step["flow"]:
                (self.warn if untested else self.err)(w, "본문 「수행 내용」이 비어 있음"
                                                      + ("(미시험이면 하지 않은 이유를 적음)" if untested else ""))
            self.collect_evidence(sid, p, p.section("증거"), masked, "red")
            steps_by_s[sid.split("-")[0]].append(step)
        out = []
        for p in self.by_db.get("R4", []):
            scid = p.prop("시나리오 ID")
            w = f"R4 {scid or p.title}"
            masked = p.flag("마스킹 완료") or "마스킹 완료: 예" in text_of(p.blocks[:3])
            cards = [{"card": r.get("위협 카드", ""), "reason": r.get("사용 사유", ""), "approver": r.get("승인자", ""),
                      "used_at": r.get("사용 시각(초)", "")} for r in first_table(p.section("위협 카드"))]
            impact = kv_table(p.section("영향 분석"))
            diagram = p.section("공격 체인 다이어그램")
            sc = {
                "scenario_id": self.need(p, "시나리오 ID", w), "name": p.title,
                "objective_ids": p.ids("목표"),
                "start_condition": self.enum(p, "시작 조건", START, w),
                "result_summary": p.prop("결과 요약"),
                "scope_note": p.prop("확인 범위"),
                "performed": p.prop("수행일"),
                "authors": split_names(p.prop("작성자")),
                "threat_cards": [c for c in cards if c["card"]],
                "impact": {"data": impact.get("유출·변조될 수 있는 정보", ""), "service": impact.get("서비스 영향", ""),
                           "if_real": impact.get("실제 사고였다면", ""), "severity_gap": impact.get("개별 위험도와의 차이", "")},
                "diagram": first_code(diagram),
                "clues": self.collect_flow(scid, p, p.section("단서와 경로 선택"), masked, "red", code_as_evidence=False),
                "pitfalls": [{"kind": r.get("구분", ""), "text": r.get("내용", ""), "step_ids": split_ids(r.get("관련 단계", "")),
                              "control": r.get("원인 / 막은 통제", "") or r.get("원인/막은 통제", "")}
                             for r in first_table(p.section("주의점과 실패한 시도")) if r.get("내용")],
                "causes": list_items(p.section("성립 원인")) or split_names(text_of(p.section("성립 원인"))),
                "cleanup": [{"item": r.get("대상에 남긴 것", ""), "where": r.get("위치", ""),
                             "done": r.get("정리 여부", ""), "how": r.get("정리 일시 · 확인 방법", "") or r.get("정리 일시·확인 방법", "")}
                            for r in first_table(p.section("정리 내역")) if r.get("대상에 남긴 것")],
                "blocking": [{"point": r.get("차단 지점", ""), "steps": r.get("끊기는 단계", ""), "advice": r.get("권고", ""),
                              "finding_ids": split_ids(r.get("관련 취약점", "")), "blue": r.get("탐지 보완", "")}
                             for r in first_table(p.section("경로 차단 권고")) if r.get("차단 지점")],
                "steps": sorted(steps_by_s.get(scid, []), key=lambda s: id_key(s["step_id"])),
            }
            self.collect_evidence(scid, p, [b for b in diagram if b.type == "image"], masked, "red", code_as_evidence=False)
            out.append(sc)
        known = {s["scenario_id"] for s in out}
        for sid, steps in steps_by_s.items():
            if sid not in known:
                self.err(f"R5 {steps[0]['step_id']}", f"단계의 시나리오 {sid}가 R4에 없음", "R-03")
        return sorted(out, key=lambda s: id_key(s["scenario_id"]))

    def patches(self) -> list[dict]:
        ps = sorted(self.by_db.get("R6", []), key=lambda p: (p.prop("적용 일자"), p.title))
        out = []
        for n, p in enumerate(ps, 1):
            w = f"R6 {p.title}"
            out.append({
                "patch_id": f"P-{n:02d}", "title": p.title, "instance_ids": p.ids("대상 건"),
                "type": self.enum(p, "조치 구분", PATCH_TYPE, w), "scope": self.enum(p, "적용 범위", PATCH_SCOPE, w),
                "applied_on": self.need(p, "적용 일자", w)[:10], "owner": self.need(p, "적용 담당", w),
                "change_location": p.prop("변경 위치"), "change_detail": first_code(p.section("변경 내용")),
            })
        return out

    def retests(self, patches: list[dict]) -> list[dict]:
        out = []
        by_title = {p["title"]: p["patch_id"] for p in patches}
        for p in self.by_db.get("R7", []):
            w = f"R7 {p.title}"
            ids = [by_title[t.strip()] for t in split_list(p.prop("확인한 조치")) if t.strip() in by_title]
            if not ids:
                ids = [x["patch_id"] for x in patches if p.title in x["instance_ids"]]
            chain_raw = p.prop("시나리오 재현")
            masked = p.flag("마스킹 완료")
            out.append({
                "instance_id": p.title, "patch_ids": ids, "retested_on": self.need(p, "재진단 일자", w)[:10],
                "result": self.enum(p, "결과", {"조치 완료": "fixed", "부분 조치": "partial", "미조치": "open"}, w),
                "chain_blocked": CHAIN.get(chain_raw) if chain_raw else None,
            })
            self.collect_evidence(p.title, p, p.blocks, masked, "red", code_as_evidence=False)
        return out

    # ── 블루팀 ──
    def blue(self) -> dict:
        b: dict = {}
        b1 = (self.by_db.get("B1") or [None])[0]
        if b1:
            env = kv_table(b1.section("와주 구성"))
            b["monitoring_env"] = {
                "wazuh_version": env.get("와주 버전", ""), "deployment": env.get("구성", ""),
                "design_notes": list_items(b1.section("설계 판단")),
                "maturity": {"current": env.get("현재 성숙도", ""), "next": env.get("다음 성숙도", ""),
                             "conditions": env.get("다음 단계 조건", "")},
            }
            self.collect_evidence("B1", b1, b1.section("구성도"), True, "blue", code_as_evidence=False)
            # 사진 자리(2026-11-16): 「ATT&CK Navigator」 → 4-2, 「대시보드」 → 부록 C
            self.collect_evidence("4-2", b1, b1.section("ATT&CK Navigator"), True, "blue", code_as_evidence=False)
            self.collect_evidence("B1-dash", b1, b1.section("대시보드"), True, "blue", code_as_evidence=False)
            rp = kv_table(b1.section("알림 및 대응 절차"))
            b["response_procedure"] = {
                "channels": split_list(rp.get("알림 경로", "")),
                "min_level": to_int(rp.get("알림 기준 레벨")), "owners": split_list(rp.get("담당자", "")),
                "check_interval": rp.get("확인 주기", ""), "steps": list_items(b1.section("대응 단계")),
            }
            vc = kv_table(b1.section("검증 조건"))
            b["verification_conditions"] = {
                "mode": VERIFY_MODE.get(vc.get("검증 방식", ""), vc.get("검증 방식", "")),
                "tester_ip_allowed": vc.get("테스터 IP 허용", "").lower() in YES,
                "active_response_enabled": vc.get("Active Response", "").lower() in YES,
                "ruleset": {"base_version": vc.get("기본 룰셋 버전", ""),
                            "custom_rule_ids": rule_nums(vc.get("커스텀 룰", ""))},
                "ntp_checked": vc.get("NTP 확인", "").lower() in YES,
                "period": {"start": vc.get("적용 시작(초)", ""), "end": vc.get("적용 종료(초)", "")},
            }
        b["log_sources"] = []
        for p in self.by_db.get("B2", []):
            w = f"B2 {p.title}"
            b["log_sources"].append({
                "source": p.title, "asset_id": self.need(p, "자산", w), "agent": p.prop("에이전트"),
                "path": p.prop("경로"), "collected": p.flag("수집"),
                "decoder": self.enum(p, "디코더", DECODER, w, default="none"),
                "rule_ids": rule_nums(p.prop("관련 룰")),
                "captured_at": p.prop("기준선 시각(초)"),
            })
        b["modules"] = []
        for p in self.by_db.get("B3", []):
            w = f"B3 {p.prop('모듈')}"
            b["modules"].append({
                "module": self.enum(p, "모듈", MODULE, w), "asset_ids": split_ids(p.prop("대상 자산")),
                "config_summary": p.prop("설정 요약"),
                "ar_trigger_rule_ids": rule_nums(p.prop("AR 트리거 룰")),
                "ar_action": p.prop("AR 동작"), "ar_timeout_sec": to_int(p.prop("AR 유지 시간(초)")),
            })
        b["test_cases"] = []
        for p in self.by_db.get("B4", []):
            tid = p.prop("테스트 ID")
            w = f"B4 {tid or p.title}"
            masked = p.flag("마스킹 완료")
            alerts = []
            for r in first_table(p.section("경보")):
                alerts.append({"rule_id": to_int(r.get("rule.id")), "level": to_int(r.get("level")),
                               "agent": r.get("에이전트", ""), "alert_at": r.get("경보 시각(초)", "")})
            score_raw = p.prop("점수")
            tc = {
                "test_id": self.need(p, "테스트 ID", w), "procedure": p.title,
                "source": self.enum(p, "출처", TEST_SOURCE, w), "source_ref": p.prop("출처 ID"),
                "tactic": self.need(p, "전술", w), "technique": self.need(p, "ATT&CK 기법", w),
                "expected_observable": self.need(p, "기대 관측치", w),
                "status": self.enum(p, "상태", TEST_STATUS, w, default="planned"),
                "executed_at": p.prop("실행 시각(초)"), "source_ip": p.prop("출발지 IP"),
                "outcome": self.enum(p, "결과 분류", OUTCOME, w, required=False),
                "score": int(score_raw) if score_raw.isdigit() else None,
                "gap": self.enum(p, "공백", GAP, w, required=False),
                "alerts": alerts,
                "triage": {k: v for k, v in {
                    "ack_at": p.prop("확인 시각(초)"), "verdict": TRIAGE.get(p.prop("판단")),
                    "action": p.prop("조치"), "resolved_at": p.prop("조치 완료 시각(초)"),
                    "owner": p.prop("대응 담당")}.items() if v},
                "fix_ids": p.ids("개선 조치"), "masked": masked,
            }
            self.collect_evidence(tid, p, p.section("증거"), masked, "blue")
            b["test_cases"].append({k: v for k, v in tc.items() if v not in ("", None) or k in ("score",)})
        b["test_cases"].sort(key=lambda t: id_key(t["test_id"]))
        b["detection_fixes"] = []
        for p in self.by_db.get("B5", []):
            fid = p.prop("조치 ID")
            w = f"B5 {fid or p.title}"
            masked = p.flag("마스킹 완료")
            val = first_table(p.section("검증"))
            sc_after = p.prop("재검증 점수")
            fx = {
                "fix_id": self.need(p, "조치 ID", w), "name": p.title, "test_ids": p.ids("관련 테스트"),
                "goal": self.need(p, "목표", w),
                "categorization": {"technique": p.prop("ATT&CK 기법"),
                                   "gap": self.enum(p, "공백", GAP, w, default="none")},
                "priority": {"level": to_int(p.prop("룰 level")), "rationale": p.prop("level 근거")},
                "rule_ids": rule_nums(p.prop("rule.id")),
                "files": split_list(p.prop("파일")),
                "log_sample": first_code(p.section("원본 로그 예시")),
                "rule_source": first_code(p.section("룰 전문")),
                "blind_spots": list_items(p.section("사각지대·가정")),
                "false_positives": list_items(p.section("오탐")),
                "validation": {"procedure": val[0].get("재현 절차", ""), "expected_alert": val[0].get("기대 경보", ""),
                               "result": val[0].get("결과", "")} if val else {},
                "response": list_items(p.section("대응")),
                "tuning": [{"period": r.get("관찰 기간", ""), "alerts": to_int(r.get("경보 건수")),
                            "false_positives": to_int(r.get("오탐 건수")), "cause": r.get("오탐 원인", ""),
                            "action": r.get("조치", "")} for r in first_table(p.section("오탐 튜닝 기록"))],
                "retest": {
                    "at": p.prop("재검증 시각(초)"),
                    "ack_at": p.prop("재검증 확인 시각(초)"),   # 선택: 재검증 경보를 블루팀이 확인한 시각(4점 근거)
                    "score_after": int(sc_after) if sc_after.isdigit() else None,
                    "outcome_after": OUTCOME.get(p.prop("재검증 결과")),
                    "variants": [{"procedure": r.get("수행 내용", ""), "outcome": OUTCOME.get(r.get("결과 분류", "")),
                                  "score": to_int(r.get("점수"))} for r in first_table(p.section("변형 공격"))],
                },
                "masked": masked,
            }
            self.collect_evidence(fid + ":retest", p, p.section("재검증 증거"), masked, "blue")
            b["detection_fixes"].append(fx)
        b["detection_fixes"].sort(key=lambda f: id_key(f["fix_id"]))
        b6 = (self.by_db.get("B6") or [None])[0]
        if b6:
            ov = kv_table(b6.section("개요"))
            # 침해사고 분석 페이지의 사진(경보 화면·로그 화면 등) → 9장
            self.collect_evidence("B6", b6, [x for x in b6.blocks if x.type == "image"], True, "blue",
                                  code_as_evidence=False)
            b["incident"] = {
                "scenario_id": ov.get("시나리오", ""),
                "timeline": [{"at": r.get("시각(초)", ""), "source": r.get("출처", ""),
                              "attacker_action": r.get("공격자 행위", ""), "defender_action": r.get("방어 측 활동", "")}
                             for r in first_table(b6.section("타임라인"))],
                "detection": {"first_seen_at": ov.get("최초 인지 시각(초)", ""), "basis": ov.get("판단 근거", "")},
                "containment": list_items(b6.section("봉쇄·제거·복구")),
                "impact": {"asset_ids": split_ids(ov.get("영향 자산", "")), "data": ov.get("영향 데이터", "")},
                "iocs": [{"type": r.get("종류", ""), "value": r.get("값", "")} for r in first_table(b6.section("IOC"))],
                "post_actions": list_items(b6.section("사후 활동")),
            }
        b["sca_results"] = [{
            "policy": p.title, "asset_id": p.prop("자산"), "score_before": to_float(p.prop("조치 전 점수")),
            "score_after": to_float(p.prop("조치 후 점수")), "failed_items": split_list(p.prop("주요 미통과 항목")),
            "vuln_packages_before": to_int(p.prop("취약 패키지(전)")),
            "vuln_packages_after": to_int(p.prop("취약 패키지(후)")), "captured_at": p.prop("조회 시각(초)"),
        } for p in self.by_db.get("B7", [])]
        b["cloud_watch"] = [{
            "target": CLOUD.get(p.title, p.title), "event_examples": split_list(p.prop("이벤트 예시")),
            "collected": p.flag("수집"), "rule_ids": rule_nums(p.prop("탐지 룰")),
            "notes": p.prop("비고"),
        } for p in self.by_db.get("B8", [])]
        b["improvement_tasks"] = [{
            "title": p.title, "gap": GAP.get(p.prop("관련 공백"), "none"), "test_ids": p.ids("관련 테스트"),
            "fix_ids": p.ids("관련 조치"), "owner": p.prop("담당"), "due": p.prop("기한")[:10],
            "status": TASK_STATUS.get(p.prop("상태"), "todo"),
        } for p in self.by_db.get("B9", [])]
        b10 = (self.by_db.get("B10") or [None])[0]
        if b10:
            per = first_table(b10.section("집계 기간"))
            per0 = per[0] if per else {}
            b["ops_stats"] = {
                "period": {"start": per0.get("시작일", ""), "end": per0.get("종료일", "")},
                "alerts_total": to_int(per0.get("전체 경보")), "false_positives": to_int(per0.get("오탐")),
                "alerts_by_period": [{"period": r.get("기간", ""), "count": to_int(r.get("경보 건수"))}
                                     for r in first_table(b10.section("기간별 경보"))],
                "top_rules": [{"rule_id": to_int(r.get("rule.id")), "count": to_int(r.get("건수"))}
                              for r in first_table(b10.section("많이 발생한 룰"))][:10],
            }
        return b

    def run(self) -> dict:
        data = {"project": self.project(), "assets": self.assets(), "objectives": self.objectives()}
        if any(self.by_db.get(k) for k in ("R1", "R2", "R3", "R4", "R5", "R6", "R7")):
            data["findings"] = self.findings()
            data["instances"] = self.instances()
            data["check_items"] = self.check_items()
            data["scenarios"] = self.scenarios()
            data["patches"] = self.patches()
            data["retests"] = self.retests(data["patches"])
        if any(self.by_db.get(f"B{i}") for i in range(1, 11)):
            data["blue"] = self.blue()
        return data


# ── 보조 함수 ──────────────────────────────────────────────────
def parse_location(access: str) -> dict:
    m = METHOD_RE.search(access or "")
    if not m:
        return {"url": (access or "").strip(), "method": "", "param": ""}
    method, url = m.group(1), m.group(2)
    params = re.findall(r"[?&]([A-Za-z0-9_\-\[\]]+)=", url) + re.findall(r"\{([A-Za-z0-9_]+)\}", url)
    return {"url": url, "method": method, "param": ", ".join(dict.fromkeys(params))}


def code_kind(text: str) -> str:
    s = text.lstrip()
    if re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) \S+ HTTP/", s) or s.startswith("HTTP/"):
        return "http"
    if s.startswith("{") or s.startswith("["):
        return "alert_json"
    return "log"


def split_names(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,\n]", s or "") if x.strip()]


def split_list(s: str, sep: str = r",\s*") -> list[str]:
    return [x.strip() for x in re.split(sep, s or "") if x.strip()]


def to_int(s) -> int | None:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def to_float(s) -> float | None:
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def _facts(blocks: list[Block]) -> list[str]:
    """「결과」 본문의 문장. 그림 바로 뒤 문단은 캡션이라 뺌."""
    out = []
    for n, b in enumerate(blocks):
        if b.type not in ("paragraph", "bullet", "numbered") or heading_level(b) or not b.text.strip():
            continue
        if b.type == "paragraph" and n and blocks[n - 1].type == "image":
            continue
        out.append(b.text.strip())
    return out


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                        "september", "october", "november", "december"], 1)}


def to_kst(raw: str) -> str:
    """노션 날짜 값 → 「YYYY-MM-DDTHH:MM:SS+09:00」(시각이 없으면 「YYYY-MM-DD」). 읽지 못하면 빈 문자열.

    받는 형태: API ISO(…Z, …+00:00, …+09:00), 「2026-11-13 22:37」, 「November 13, 2026 10:37 PM」(CSV 내보내기),
    「2026/11/13 22:37 (GMT+9)」. 구간(→)이면 앞 값만 씀
    """
    from datetime import datetime, timedelta, timezone
    s = (raw or "").split("→")[0].strip()
    if not s:
        return ""
    kst = timezone(timedelta(hours=9))
    s2 = re.sub(r"\s*\((GMT|UTC)[^)]*\)\s*$", "", s).replace("/", "-")
    try:
        d = datetime.fromisoformat(s2.replace("Z", "+00:00"))
        if len(s2) == 10:
            return s2
        if d.tzinfo is None:
            d = d.replace(tzinfo=kst)
        return d.astimezone(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    except ValueError:
        pass
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AP]M)?)?", s2, re.I)
    if m and m.group(1).lower() in MONTHS:
        y, mo, d = int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))
        if m.group(4) is None:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        h, mi, se = int(m.group(4)), int(m.group(5)), int(m.group(6) or 0)
        ap = (m.group(7) or "").upper()
        if ap == "PM" and h < 12:
            h += 12
        if ap == "AM" and h == 12:
            h = 0
        return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{se:02d}+09:00"
    return ""


CAPTION_TAIL_RE = re.compile(r"(화면|요청|응답|요청·응답|로그|결과|출력)(\s*\([^)]*\))?$")


def merge_image_captions(blocks: list[Block]) -> list[Block]:
    """그림 바로 아래 짧은 문단(「… 화면」 형태)을 그 그림의 캡션으로 옮김. 본문 글로 두 번 나오지 않게 함."""
    out: list[Block] = []
    skip = -1
    for i, b in enumerate(blocks):
        if i == skip:
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if (b.type == "image" and nxt is not None and nxt.type == "paragraph" and len(nxt.text.strip()) <= 90
                and CAPTION_TAIL_RE.search(nxt.text.strip()) and not clean_caption(b.text)):
            b = Block(type="image", text=nxt.text.strip(), path=b.path)
            skip = i + 1
        out.append(b)
    return out


def id_key(s: str) -> tuple:
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s or ""))


RANGE_RE = re.compile(r"(\d+)\s*[~∼〜]\s*(\d+)|(\d+)\s*-\s*(\d+)(?=\D|$)|(\d+)")


def rule_nums(s: str) -> list[int]:
    """룰 번호 목록. 「100101~100126」 같은 범위는 펼침(피드백: 두 숫자만 읽혀 「100101, 100126」으로 나옴)."""
    out: list[int] = []
    for m in RANGE_RE.finditer(s or ""):
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if a and b and int(a) <= int(b) and int(b) - int(a) <= 500 and len(a) == len(b):
            out += list(range(int(a), int(b) + 1))
        elif a and b:
            out += [int(a), int(b)]
        else:
            out.append(int(m.group(5)))
    return out


FILENAME_CAPTION_RE = re.compile(
    r"(\.(png|jpe?g|gif|webp|bmp|heic)$)|^(image|untitled|screenshot|스크린샷|화면 ?캡처|캡처)[\s_\-\d.:]*", re.I)


def clean_caption(text: str) -> str:
    """노션 그림 캡션에서 파일 이름(image.png, Screenshot 2026-… .png, 스크린샷 …)을 걸러 냄."""
    t = (text or "").strip().strip("[] ").replace("\u202f", " ")
    if not t or FILENAME_CAPTION_RE.search(t):
        return ""
    return t


SKIP_LINES = ("write-up", "writeup", "---")   # 비교 전 공백·강조 기호를 뺌


def build_flow(blocks: list[Block], refs: dict[int, str]) -> list[dict]:
    """본문 블록 → 흐름 조각 목록. {"text": 여러 줄} | {"ref": 증거 키} | {"code": 내용, "lang": 언어}.

    이어진 글 블록은 한 조각으로 묶음(AI 다듬기 단위). 목록은 「- 」·「1. 」을 붙여 그대로 둠.
    """
    flow: list[dict] = []
    buf: list[str] = []

    def flush():
        if buf:
            flow.append({"text": "\n".join(buf)})
            buf.clear()

    for i, b in enumerate(blocks):
        if b.type == "image":
            flush()
            if i in refs:
                flow.append({"ref": refs[i]})
        elif b.type == "code":
            flush()
            if b.text.strip():
                flow.append({"code": textwrap.dedent(b.text).strip("\n"), "lang": b.lang, **({"ref": refs[i]} if i in refs else {})})
        elif b.type in ("paragraph", "bullet", "numbered", "heading"):
            t = b.text.strip().replace("<br>", " ").replace("<br />", " ")
            if not t or re.sub(r"[*_`#\s]", "", t).lower() in SKIP_LINES:
                continue
            if b.type == "heading":
                t = f"**{t}**"
            elif b.type == "bullet":
                t = "- " + t
            elif b.type == "numbered":
                t = "1. " + t
            buf.append(t)
    flush()
    return flow


def _free_text(blocks: list[Block]) -> str:
    """자유 서술 본문. 토글 제목(Write-up 등) 한 줄짜리 목록은 뺌."""
    out = []
    for b in blocks:
        if b.type in ("paragraph", "bullet", "numbered") and not heading_level(b):
            t = b.text.strip()
            if t and t.lower() not in ("write-up", "writeup", "write up"):
                out.append(t.replace("<br>", " ").replace("<br />", " "))
    return "\n".join(out)


def map_pages(pages: list[Page], report: str | None = None, lenient: bool = True) -> tuple[dict, list[dict], list[dict]]:
    m = Mapper(pages, report, lenient)
    data = m.run()
    return data, m.issues, m.evidence_raw
