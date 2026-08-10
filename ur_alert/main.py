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
    """遍历 watchlist 団地,返回 (本轮命中的 Room 列表, 抓取失败的団地列表)。

    单个団地抓取失败(多为 UR API 瞬时超时)不再中断整轮:记录并跳过,
    该団地下一轮(20 分钟后)自然重试。是否升级为告警由 run() 按占比判定。
    """
    matched, failed = [], []
    for d in watch:
        try:
            raw_rooms = ur_api.get_vacant_rooms(
                d["shisya"], d["danchi"], d["shikibetu"], config.BLOCK, config.TDFK
            )
        except Exception as exc:  # noqa: BLE001  隔离单団地故障,保证其余団地照常检查
            failed.append(d)
            print(f"⚠ 団地抓取失败,跳过:{d.get('danchiNm') or d.get('danchi')} — {exc}",
                  file=sys.stderr)
            continue
        for raw in raw_rooms:
            room = parse_room(raw, d.get("danchiNm", ""))
            if matches(room):
                matched.append(room)
        time.sleep(0.2)
    return matched, failed


def run():
    watch = load_watchlist()
    print(f"监控団地数: {len(watch)}")

    matched, failed = collect_matches(watch)
    print(f"本轮命中部屋数(全量): {len(matched)}")
    if failed:
        names = ", ".join(d.get("danchiNm") or d.get("danchi") for d in failed)
        print(f"⚠ 本轮 {len(failed)}/{len(watch)} 个団地抓取失败(已跳过): {names}",
              file=sys.stderr)

    seen = state.load_seen(config.STATE_PATH)
    new = [r for r in matched if r.id and r.id not in seen]

    notify(new)

    matched_ids = {r.id for r in matched if r.id}
    # 全部成功:用本轮覆盖(空房复活会重新提醒,持续空着不重复)。
    # 有団地失败:并上上轮 seen —— 否则失败団地的旧房本轮缺席、下轮会被误报为「新」。
    state.save_seen(config.STATE_PATH, (matched_ids | seen) if failed else matched_ids)

    # 只有系统性失败(过半団地都挂 → UR 接口不可用 / 代码坏了)才告警,避免个别超时刷屏。
    if watch and len(failed) / len(watch) > config.ALERT_ON_FAILED_RATIO:
        names = ", ".join(d.get("danchiNm") or d.get("danchi") for d in failed)
        raise RuntimeError(
            f"UR API 大面积抓取失败:{len(failed)}/{len(watch)} 団地失败"
            f"(疑似 UR 接口不可用)。失败団地:{names}"
        )
    return new


if __name__ == "__main__":
    # 任何异常都先邮件告警本人(issue 07),再以非零退出让 CI 显式失败。
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        notify_error(exc)
        raise
