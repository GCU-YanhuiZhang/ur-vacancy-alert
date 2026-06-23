"""notify 单测(不联网、不真发信)。可直接跑:python tests/test_notify.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ur_alert import config, notify  # noqa: E402
from ur_alert.parse import Room  # noqa: E402


def _room(name="菊名池", room_no="402号室", madori="2K", total=66000, area=37.0):
    return Room(
        id="000000402", shisya="40", danchi="052", shikibetu="0",
        danchi_name=name, building="", room_no=room_no, madori=madori,
        rent=(total - 2900) if total else None, commonfee=2900,
        total_rent=total, area=area, floor="4階", rent_raw="", detail_url="http://x",
    )


def test_build_message_single():
    s, b = notify.build_message([_room()])
    assert "新 1 件" in s and "菊名池" in s
    assert "66,000円" in b and "37㎡" in b and "勝どき≤55分" in b


def test_build_message_multiple_hoka():
    s, _ = notify.build_message([_room(), _room(name="鶴見町")])
    assert "新 2 件" in s and "ほか" in s


def test_email_message_headers():
    config.GMAIL_USER = "sender@gmail.com"
    config.MAIL_TO = "recipient@example.com"
    config.MAIL_CC = "sender@gmail.com"
    msg = notify.build_email_message("subj", "body text")
    assert msg["From"] == "sender@gmail.com"
    assert msg["To"] == "recipient@example.com"
    assert msg["Cc"] == "sender@gmail.com"
    assert msg["Subject"] == "subj"
    assert "body text" in msg.get_content()


def test_notify_empty_no_crash():
    notify.notify([])  # 无新空房:仅打印,不发信,不抛错


def test_build_error_message_has_traceback():
    try:
        raise ValueError("UR API 请求失败")
    except ValueError as exc:
        s, b = notify.build_error_message(exc)
    assert "告警" in s and "ValueError" in s
    assert "UR API 请求失败" in b and "traceback" in b and "ValueError" in b


def test_notify_error_no_creds_no_crash():
    # 未配置凭据:告警退化为打印,不抛错
    config.GMAIL_USER = ""
    config.GMAIL_APP_PASSWORD = ""
    notify.notify_error(RuntimeError("boom"))


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"PASSED {len(fns)} tests")
