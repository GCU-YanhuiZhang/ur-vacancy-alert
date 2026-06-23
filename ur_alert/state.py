"""快照状态:上一轮命中部屋 ID 集合的读写(state/seen.json)。

差集语义见 PRD:新空房 = 本轮命中 − 上轮命中;跑完用本轮覆盖。
"""
import json
from pathlib import Path


def load_seen(path):
    p = Path(path)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        # 状态文件损坏 → 当作空集(代价:本轮可能多发一次,不会漏)
        return set()


def save_seen(path, ids):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=1), encoding="utf-8")
