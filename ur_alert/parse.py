"""把 UR room 接口的原始 dict 解析成规范化的 Room。

解析坑(见 PRD):家賃 "43,000円" 带千分位;面积是 HTML 实体 &#13217;=㎡;
家賃偶尔是范围 "50,000円〜67,000円"(取最小值,保守不漏)。
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

_NUM = re.compile(r"\d[\d,]*")


@dataclass
class Room:
    id: str
    shisya: str
    danchi: str
    shikibetu: str
    danchi_name: str
    building: str        # 棟  (roomNmMain, 如 "1-21号棟")
    room_no: str         # roomNmSub (如 "407号室")
    madori: str          # 間取り (type, 如 "2DK")
    rent: int | None     # 家賃(円)
    commonfee: int       # 共益費(円)
    total_rent: int | None   # 家賃 + 共益費
    area: float | None   # 面积(㎡)
    floor: str           # 楼层(原文, 如 "4階")
    rent_raw: str        # 家賃原文(用于展示/排错)
    detail_url: str      # 部屋详情页


def parse_yen_min(s):
    """从含日元的字符串里取最小数值;范围/多值时取最小(保守,避免漏)。"""
    if not s:
        return None
    nums = [int(m.replace(",", "")) for m in _NUM.findall(s)]
    return min(nums) if nums else None


def parse_area(s):
    """面积字符串(可能含 HTML 实体)→ float ㎡。"""
    if not s:
        return None
    m = re.search(r"\d+(?:\.\d+)?", html.unescape(s))
    return float(m.group(0)) if m else None


def parse_room(raw, danchi_name=""):
    rent_raw = raw.get("rent_normal") or raw.get("rent") or ""
    rent = parse_yen_min(rent_raw)
    commonfee = parse_yen_min(raw.get("commonfee")) or 0
    total = rent + commonfee if rent is not None else None

    detail = raw.get("roomLinkPc") or ""
    if detail.startswith("/"):
        detail = "https://www.ur-net.go.jp" + detail

    return Room(
        id=raw.get("id") or "",
        shisya=raw.get("shisya", ""),
        danchi=raw.get("danchi", ""),
        shikibetu=raw.get("shikibetu", ""),
        danchi_name=danchi_name,
        building=raw.get("roomNmMain") or "",
        room_no=raw.get("roomNmSub") or "",
        madori=raw.get("type") or "",
        rent=rent,
        commonfee=commonfee,
        total_rent=total,
        area=parse_area(raw.get("floorspace")),
        floor=raw.get("floor") or "",
        rent_raw=rent_raw,
        detail_url=detail,
    )
