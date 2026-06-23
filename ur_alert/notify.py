"""通知:把新命中部屋格式化并通过 Gmail SMTP 发邮件。

凭据见 config(环境变量)。未配置凭据时退化为打印(本地/CI 无 secrets 也不报错)。
不发空邮件:本轮无新空房则不发(避免噪声)。
"""
import smtplib
import ssl
import traceback
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from . import config

_JST = timezone(timedelta(hours=9))


def format_rooms(rooms):
    lines = []
    for r in rooms:
        if r.total_rent is not None:
            rent = f"{r.total_rent:,}円(家賃+共益費)"
        else:
            rent = f"{r.rent_raw or '?'}(家賃解析失败,请人工核对)"
        area = f"{r.area:g}㎡" if r.area is not None else "?㎡"
        lines.append(
            f"・{r.danchi_name} {r.building}{r.room_no} | {r.madori} | {rent} | {area} | {r.floor}\n"
            f"  {r.detail_url}"
        )
    return "\n".join(lines)


def build_message(new_rooms):
    """返回 (subject, body)。"""
    n = len(new_rooms)
    first = new_rooms[0].danchi_name if new_rooms else ""
    extra = "ほか" if n > 1 else ""
    subject = f"【UR空房】新 {n} 件 | {first}{extra}"
    ts = datetime.now(_JST).strftime("%Y-%m-%d %H:%M JST")
    body = (
        f"UR 新空房 {n} 件\n"
        f"条件:勝どき≤55分(门到门) / 家賃+共益費≤8万 / 1K以上 / ≥20㎡\n"
        f"检查时间:{ts}\n\n"
        f"{format_rooms(new_rooms)}\n\n"
        f"— ur-vacancy-alert"
    )
    return subject, body


def build_email_message(subject, body):
    """构造 EmailMessage(便于单测,不发送)。"""
    msg = EmailMessage()
    msg["From"] = config.GMAIL_USER
    msg["To"] = config.MAIL_TO
    if config.MAIL_CC and config.MAIL_CC != config.MAIL_TO:
        msg["Cc"] = config.MAIL_CC
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def send_email(subject, body):
    msg = build_email_message(subject, body)
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=30) as s:
            s.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            s.send_message(msg)
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"Gmail 发信失败: {exc}") from exc


def notify(new_rooms):
    if not new_rooms:
        print("本轮无新空房命中,不发邮件。")
        return
    subject, body = build_message(new_rooms)
    if config.email_configured():
        send_email(subject, body)
        cc = f" (cc {config.MAIL_CC})" if config.MAIL_CC and config.MAIL_CC != config.MAIL_TO else ""
        print(f"已发邮件:{subject} → {config.MAIL_TO}{cc}")
    else:
        print("⚠ 邮件凭据未配置(GMAIL_USER / GMAIL_APP_PASSWORD),改为打印:\n")
        print(subject)
        print(body)


def build_error_message(exc):
    """脚本异常告警邮件 (subject, body)。含异常类型/消息/traceback,便于排查。"""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    ts = datetime.now(_JST).strftime("%Y-%m-%d %H:%M JST")
    subject = f"【UR空房·告警】脚本异常: {type(exc).__name__}"
    body = (
        f"ur-vacancy-alert 本轮运行失败,可能漏报,请检查。\n"
        f"时间:{ts}\n"
        f"异常:{type(exc).__name__}: {exc}\n\n"
        f"--- traceback ---\n{tb}\n"
        f"— ur-vacancy-alert"
    )
    return subject, body


def notify_error(exc):
    """脚本异常时通知本人(issue 07)。发信本身失败不再抛,以免吞掉原始异常。"""
    subject, body = build_error_message(exc)
    if config.email_configured():
        try:
            send_email(subject, body)
            print(f"已发告警邮件:{subject} → {config.MAIL_TO}")
        except Exception as send_exc:  # noqa: BLE001  告警发信失败:仅打印,不掩盖原异常
            print(f"⚠ 告警邮件发送失败:{send_exc}")
    else:
        print("⚠ 邮件凭据未配置,告警改为打印:\n")
        print(subject)
        print(body)


if __name__ == "__main__":
    # 手动验证发信:配好 .env 后 `python -m ur_alert.notify` 会发一封测试邮件。
    if config.email_configured():
        send_email("【UR空房】测试邮件", "这是一封 ur-vacancy-alert 的测试邮件,收到即说明 SMTP 配置正确。")
        print(f"测试邮件已发 → {config.MAIL_TO}")
    else:
        print("未配置 GMAIL_USER / GMAIL_APP_PASSWORD,无法发测试邮件。")
