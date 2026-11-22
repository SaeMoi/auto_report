"""테스트 계정 본문 5개 고르기(2026-11-22): 권한마다 첫 계정 우선, 남는 자리는 표 순서, 표 순서 유지."""
from reportgen.render.markdown import _pick_accounts


def _a(*pairs):
    return [{"name": n, "role": r} for n, r in pairs]


def test_each_role_first_then_table_order():
    accts = _a(("a", "회원"), ("b", "회원"), ("c", "회원"), ("d", "회원"), ("e", "회원"),
               ("f", "강사"), ("g", "관리자"), ("h", "회원"))
    got = [t["name"] for t in _pick_accounts(accts, 5)]
    assert got == ["a", "b", "c", "f", "g"]   # 권한 3개의 첫 계정(a·f·g) + 표 순서(b·c), 표 순서로 보임


def test_more_roles_than_limit_takes_first_roles():
    accts = _a(*[(f"u{i}", f"r{i}") for i in range(7)])
    assert [t["name"] for t in _pick_accounts(accts, 5)] == ["u0", "u1", "u2", "u3", "u4"]


def test_short_list_unchanged():
    accts = _a(("a", "x"), ("b", "x"))
    assert _pick_accounts(accts, 5) == accts
