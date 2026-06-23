"""编排:遍历 watchlist 団地 → 抓空房 → 解析过滤 → 快照差集 → 通知 → 存状态。

运行:python -m ur_alert.main
"""
import json
import sys
import time
from pathlib import Path

from . import config, state, ur_api
from .filter import matches
from .notify import notify, notify_error
from .parse import parse_room


def load_watchlist():
    """读 watchlist.json(団地三元组列表)。不存在则回退抓全神奈川団地。"""
    p = Path(config.WATCHLIST_PATH)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    print("⚠ watchlist.json 不存在,回退抓取全神奈川団地(未按通勤筛选)", file=sys.stderr)
    return [
        {"shisya": d["shisya"], "danchi": d["danchi"],
         "shikibetu": d["shikibetu"], "danchiNm": d.get("danchiNm", "")}
        for d in ur_api.list_danchi(config.BLOCK, config.TDFK)
    ]


def collect_matches(watch):
    """遍历 watchlist 団地,返回本轮所有命中的 Room。"""
    matched = []
    for i, d in enumerate(watch, 1):
        raw_rooms = ur_api.get_vacant_rooms(
            d["shisya"], d["danchi"], d["shikibetu"], config.BLOCK, config.TDFK
        )
        for raw in raw_rooms:
            room = parse_room(raw, d.get("danchiNm", ""))
            if matches(room):
                matched.append(room)
        time.sleep(0.2)
    return matched


def run():
    watch = load_watchlist()
    print(f"监控団地数: {len(watch)}")

    matched = collect_matches(watch)
    print(f"本轮命中部屋数(全量): {len(matched)}")

    seen = state.load_seen(config.STATE_PATH)
    new = [r for r in matched if r.id and r.id not in seen]

    notify(new)

    # 用本轮命中集合覆盖状态(空房复活会重新提醒,持续空着不重复)
    state.save_seen(config.STATE_PATH, {r.id for r in matched if r.id})
    return new


if __name__ == "__main__":
    # 任何异常都先邮件告警本人(issue 07),再以非零退出让 CI 显式失败。
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        notify_error(exc)
        raise
