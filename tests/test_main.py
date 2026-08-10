"""main 编排层单测:重点验证容错(单団地失败不刷屏、系统性失败才告警)。

不联网:monkeypatch 掉 ur_api / notify / state。可直接跑:python tests/test_main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ur_alert import config, main  # noqa: E402


# --- 极简打桩:不引入 pytest 依赖,手动替换模块属性,跑完还原 ---

def _patch(watch, fail_danchi=(), rooms_by_danchi=None):
    """把 main 依赖替换成可控假实现,返回 (还原函数, 通知记录, 保存的状态盒子)。"""
    rooms_by_danchi = rooms_by_danchi or {}
    orig = {k: getattr(main, k) for k in ("load_watchlist", "notify", "parse_room", "matches")}
    orig_api = main.ur_api.get_vacant_rooms
    orig_state = (main.state.load_seen, main.state.save_seen)

    saved = {"ids": None}
    sent = {"rooms": None}

    def fake_get_vacant_rooms(shisya, danchi, shikibetu, *a, **k):
        if danchi in fail_danchi:
            raise RuntimeError(f"UR API 请求失败: read timed out ({danchi})")
        return rooms_by_danchi.get(danchi, [])

    main.load_watchlist = lambda: watch
    main.ur_api.get_vacant_rooms = fake_get_vacant_rooms
    main.parse_room = lambda raw, name: raw          # raw 已是「Room 样」对象
    main.matches = lambda room: True                 # 全部命中,聚焦编排逻辑
    main.notify = lambda new: sent.__setitem__("rooms", new)
    main.state.load_seen = lambda path: set()
    main.state.save_seen = lambda path, ids: saved.__setitem__("ids", set(ids))

    def restore():
        for k, v in orig.items():
            setattr(main, k, v)
        main.ur_api.get_vacant_rooms = orig_api
        main.state.load_seen, main.state.save_seen = orig_state

    return restore, sent, saved


class _R:
    """最小 Room 替身:只需要 .id 字段。"""
    def __init__(self, rid):
        self.id = rid


def test_single_danchi_failure_is_isolated_not_raised():
    # 3 个団地,中间那个抓取超时:整轮不应抛异常,其余両団地照常出结果。
    watch = [
        {"shisya": "40", "danchi": "A", "shikibetu": "0", "danchiNm": "甲"},
        {"shisya": "40", "danchi": "B", "shikibetu": "0", "danchiNm": "乙"},
        {"shisya": "40", "danchi": "C", "shikibetu": "0", "danchiNm": "丙"},
    ]
    restore, sent, saved = _patch(
        watch, fail_danchi=("B",),
        rooms_by_danchi={"A": [_R("a1")], "C": [_R("c1")]},
    )
    try:
        new = main.run()            # 不应抛错
        ids = {r.id for r in new}
        assert ids == {"a1", "c1"}, ids
        # 有失败 → 状态并入上轮 seen(此处 seen 为空,故等于本轮命中集)
        assert saved["ids"] == {"a1", "c1"}, saved["ids"]
    finally:
        restore()


def test_all_danchi_failure_escalates_to_alert():
    # 全部団地失败(占比 100% > 阈值)→ 判定系统性故障,抛 RuntimeError(供 __main__ 告警)。
    watch = [
        {"shisya": "40", "danchi": "A", "shikibetu": "0", "danchiNm": "甲"},
        {"shisya": "40", "danchi": "B", "shikibetu": "0", "danchiNm": "乙"},
    ]
    restore, sent, saved = _patch(watch, fail_danchi=("A", "B"))
    try:
        raised = None
        try:
            main.run()
        except RuntimeError as exc:
            raised = exc
        assert raised is not None, "全団地失败应升级为告警异常"
        assert "大面积抓取失败" in str(raised)
    finally:
        restore()


def test_minority_failure_below_threshold_no_alert():
    # 4 个団地挂 1 个(25% ≤ 50% 阈值):不告警,正常返回。
    watch = [
        {"shisya": "40", "danchi": d, "shikibetu": "0", "danchiNm": d}
        for d in ("A", "B", "C", "D")
    ]
    restore, sent, saved = _patch(
        watch, fail_danchi=("A",),
        rooms_by_danchi={"B": [_R("b1")]},
    )
    try:
        new = main.run()            # 不应抛错
        assert {r.id for r in new} == {"b1"}
    finally:
        restore()


def test_failure_preserves_prev_seen_to_avoid_respam():
    # 有失败団地时,save_seen 应并入上轮 seen,防止失败団地旧房下轮被误报为「新」。
    watch = [
        {"shisya": "40", "danchi": "A", "shikibetu": "0", "danchiNm": "甲"},
        {"shisya": "40", "danchi": "B", "shikibetu": "0", "danchiNm": "乙"},
    ]
    restore, sent, saved = _patch(
        watch, fail_danchi=("B",),
        rooms_by_danchi={"A": [_R("a1")]},
    )
    # 上轮 seen 含失败団地 B 的旧房 b_old,应被保留
    main.state.load_seen = lambda path: {"b_old"}
    try:
        main.run()
        assert saved["ids"] == {"a1", "b_old"}, saved["ids"]
    finally:
        restore()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"PASSED {len(fns)} tests")
