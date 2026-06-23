"""parse 单测。可直接跑:python tests/test_parse.py  (无需 pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ur_alert.parse import parse_area, parse_room, parse_yen_min  # noqa: E402


def test_parse_yen_plain():
    assert parse_yen_min("43,000円") == 43000


def test_parse_yen_range_takes_min():
    assert parse_yen_min("50,000円〜67,000円") == 50000


def test_parse_yen_empty():
    assert parse_yen_min("") is None
    assert parse_yen_min(None) is None


def test_parse_area_html_entity():
    assert parse_area("45&#13217;") == 45.0


def test_parse_area_decimal():
    assert parse_area("45.5㎡") == 45.5


def test_parse_room_full():
    raw = {
        "id": "000121407", "shisya": "40", "danchi": "150", "shikibetu": "0",
        "roomNmMain": "1-21号棟", "roomNmSub": "407号室", "type": "2DK",
        "rent_normal": "43,000円", "commonfee": "2,900円",
        "floorspace": "45&#13217;", "floor": "4階",
        "roomLinkPc": "/chintai/kanto/kanagawa/40_1500_room.html?JKSS=000121407",
    }
    r = parse_room(raw, danchi_name="下大槻")
    assert r.id == "000121407"
    assert r.building == "1-21号棟"
    assert r.rent == 43000
    assert r.commonfee == 2900
    assert r.total_rent == 45900
    assert r.area == 45.0
    assert r.madori == "2DK"
    assert r.danchi_name == "下大槻"
    assert r.detail_url.startswith("https://www.ur-net.go.jp/")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"PASSED {len(fns)} tests")
