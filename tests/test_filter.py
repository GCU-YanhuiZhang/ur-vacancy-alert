"""filter 单测。可直接跑:python tests/test_filter.py  (无需 pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ur_alert.filter import matches  # noqa: E402
from ur_alert.parse import Room  # noqa: E402


def _room(madori="2DK", area=45.0, rent=43000, commonfee=2900):
    total = None if rent is None else rent + (commonfee or 0)
    return Room(
        id="x", shisya="40", danchi="150", shikibetu="0", danchi_name="t",
        building="1号棟", room_no="101号室", madori=madori,
        rent=rent, commonfee=commonfee or 0, total_rent=total,
        area=area, floor="1階", rent_raw="", detail_url="",
    )


def test_typical_match():
    assert matches(_room()) is True


def test_1r_excluded():
    assert matches(_room(madori="1R")) is False


def test_area_below_min_excluded():
    assert matches(_room(area=19.9)) is False


def test_area_at_min_included():
    assert matches(_room(area=20.0)) is True


def test_rent_over_cap_excluded():
    assert matches(_room(rent=80000, commonfee=1)) is False  # total 80001


def test_rent_at_cap_included():
    assert matches(_room(rent=77100, commonfee=2900)) is True  # total 80000


def test_unknown_rent_surfaces():
    # 家賃解析失败但間取り/面积合格 → 放行(不漏优先)
    assert matches(_room(rent=None)) is True


def test_missing_area_excluded():
    assert matches(_room(area=None)) is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"PASSED {len(fns)} tests")
