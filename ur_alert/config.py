"""固定配置:命中条件 + 路径 + UR 搜索范围 + 邮件设置。

自用、单租户(ADR-0002),所以筛选条件是常量而非运行时输入。
邮件凭据从环境变量读(本地 .env / GitHub Actions secrets),绝不写进代码或入库。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "watchlist.json"        # 通勤候选団地(三元组)
STATE_PATH = ROOT / "state" / "seen.json"       # 上一轮命中部屋 ID 集合(commit 回仓库)


def _load_dotenv(path):
    """极简零依赖 .env 加载:仅在本地存在 .env 时把 KEY=VALUE 注入环境(不覆盖已有)。"""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

# --- 命中条件(固定;见 PRD)---
MAX_TOTAL_RENT = 80_000          # 家賃 + 共益費 合计上限(円)
MIN_AREA = 20.0                  # 面积下限(㎡)
EXCLUDED_MADORI = {"1R"}         # 「1K 以上」→ 仅排除 1R / 单间
TARGET_STATION = "勝どき"         # 仅作记录;通勤精度団地级(ADR-0001),已固化进 watchlist

# --- UR 搜索范围 ---
BLOCK = "kanto"
TDFK = "14"                      # 都道府県码:14 = 神奈川県

# --- 邮件(凭据来自环境变量 / .env / Actions secrets)---
GMAIL_USER = os.environ.get("GMAIL_USER", "")            # 发信 Gmail 地址
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")  # 16 位应用专用密码
MAIL_TO = os.environ.get("MAIL_TO") or GMAIL_USER        # 收件(留空=发给自己;真实收件只放 Secrets,不入库)
MAIL_CC = os.environ.get("MAIL_CC", GMAIL_USER)          # 抄送(默认=发信 Gmail 自身,163 兜底)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465                                          # SSL


def email_configured():
    return bool(GMAIL_USER and GMAIL_APP_PASSWORD)
