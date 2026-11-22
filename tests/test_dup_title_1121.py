"""같은 제목의 본문 md가 둘 있을 때(시나리오마다 「리버스 셸 획득」) 행마다 제 본문을 찾는지."""
from pathlib import Path

from reportgen.intake.notion_export import read_export


def test_same_title_bodies(tmp_path: Path):
    root = tmp_path / "exp"
    d = root / "시나리오 단계"
    d.mkdir(parents=True)
    (root / "시나리오 단계 41c5c91585918175b30bc2b0624799e1.csv").write_text(
        "단계명,단계 ID\n리버스 셸 획득,S1-STEP4\n리버스 셸 획득,S3-STEP4\n", encoding="utf-8")
    (d / "리버스 셸 획득 41c5c915859181d2b497d11e13875a59.md").write_text(
        "# 리버스 셸 획득\n\n단계 ID: S3-STEP4\n\n## 수행 내용\n\n세 번째 시나리오 본문\n", encoding="utf-8")
    (d / "리버스 셸 획득 41c5c915859181568723c31ee6b85b57.md").write_text(
        "# 리버스 셸 획득\n\n단계 ID: S1-STEP4\n\n## 수행 내용\n\n첫 번째 시나리오 본문\n", encoding="utf-8")
    pages = read_export([root], {"R5": "시나리오 단계"})
    got = {p.props.get("단계 ID"): " ".join(str(b) for b in p.blocks) for p in pages if p.db == "R5"}
    assert "첫 번째" in got["S1-STEP4"] and "세 번째" not in got["S1-STEP4"]
    assert "세 번째" in got["S3-STEP4"]
