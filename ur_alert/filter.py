"""命中判定:一个部屋是否满足全部固定条件(见 PRD / config)。

通勤(団地是否在 watchlist 内)在 main 里按団地处理,不在这里 ——
这里只判部屋级条件:間取り、面积、家賃。
"""
from .config import EXCLUDED_MADORI, MAX_TOTAL_RENT, MIN_AREA


def matches(room):
    # 間取り:1K 以上(排除 1R)
    if room.madori in EXCLUDED_MADORI:
        return False
    # 面积:≥ 下限(解析不出面积 → 视为不合格)
    if room.area is None or room.area < MIN_AREA:
        return False
    # 家賃 + 共益費:≤ 上限。
    # 注:家賃解析失败(total_rent is None)时**放行**,让人工判断 ——「不漏」优先于「不重」。
    if room.total_rent is not None and room.total_rent > MAX_TOTAL_RENT:
        return False
    return True
