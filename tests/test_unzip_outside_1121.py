"""노션 zip은 프로젝트(OneDrive) 밖 캐시에 풀고, 예전에 zip 옆에 풀어 둔 폴더는 읽지 않는지(2026-11-21)."""
import zipfile
from pathlib import Path

from reportgen.intake import notion_export
from reportgen.intake.notion_export import read_export

H = "0123456789abcdef0123456789abcdef"


def _zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)


def test_unzip_outside(tmp_path: Path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("REPORTGEN_UNZIP_DIR", str(cache))
    red = tmp_path / "proj" / "input" / "notion" / "red"
    red.mkdir(parents=True)
    _zip(red / "red_team.zip", {
        f"Red team/시나리오 단계 {H}.csv": "단계명,단계 ID\n리버스 셸 획득,S1-STEP4\n",
        f"Red team/시나리오 단계/리버스 셸 획득 {H}.md": "# 리버스 셸 획득\n\n단계 ID: S1-STEP4\n\n## 수행 내용\n\n새 본문\n",
    })
    # 예전 방식으로 zip 옆에 풀린 폴더(옛 내용): 읽지 않아야 함
    old = red / "red_team" / "Red team"
    (old / "시나리오 단계").mkdir(parents=True)
    (old / f"시나리오 단계 {H}.csv").write_text("단계명,단계 ID\n리버스 셸 획득,S1-STEP4\n", encoding="utf-8")
    (old / "시나리오 단계" / f"리버스 셸 획득 {H}.md").write_text(
        "# 리버스 셸 획득\n\n단계 ID: S1-STEP4\n\n## 수행 내용\n\n옛 본문\n", encoding="utf-8")
    before = sorted(p.name for p in red.iterdir())
    pages = [p for p in read_export([red], {"R5": "시나리오 단계"}) if p.db == "R5"]
    assert len(pages) == 1
    body = " ".join(str(b) for b in pages[0].blocks)
    assert "새 본문" in body and "옛 본문" not in body
    assert sorted(p.name for p in red.iterdir()) == before   # 프로젝트 폴더에는 아무것도 새로 만들지 않음
    assert list(cache.rglob("*.md")) and not pages[0].source.startswith("/")
    # 두 번째 실행: 캐시를 그대로 씀
    assert notion_export.unzip_all(red) == notion_export.unzip_all(red)
