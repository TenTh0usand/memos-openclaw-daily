from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


@dataclass(slots=True)
class Settings:
    memos_base_url: str
    memos_token: str
    timezone: str
    output_root: Path
    report_visibility: str
    report_tag: str
    verify_ssl: bool
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_use_ssl: bool
    smtp_use_starttls: bool
    smtp_from: str
    smtp_to: str | None
    smtp_timeout_seconds: int
    empty_reminder_subject: str
    empty_reminder_body: str
    empty_reminder_once_per_day: bool


def load_settings(env_file: str | None = None) -> Settings:
    load_dotenv(dotenv_path=env_file, override=False)

    memos_base_url = os.getenv("MEMOS_BASE_URL", "").strip().rstrip("/")
    memos_token = os.getenv("MEMOS_TOKEN", "").strip()
    if not memos_base_url:
        raise ValueError("MEMOS_BASE_URL is required.")
    if not memos_token:
        raise ValueError("MEMOS_TOKEN is required.")

    return Settings(
        memos_base_url=memos_base_url,
        memos_token=memos_token,
        timezone=os.getenv("MEMOS_TIMEZONE", "Asia/Shanghai").strip(),
        output_root=Path(os.getenv("MEMOS_OUTPUT_ROOT", "./runs")).expanduser(),
        report_visibility=os.getenv("MEMOS_REPORT_VISIBILITY", "PRIVATE").strip().upper(),
        report_tag=os.getenv("MEMOS_REPORT_TAG", "daily-report").strip().lstrip("#"),
        verify_ssl=_parse_bool(os.getenv("MEMOS_VERIFY_SSL"), True),
        smtp_host=os.getenv("SMTP_HOST", "").strip() or None,
        smtp_port=int(os.getenv("SMTP_PORT", "25").strip()),
        smtp_username=os.getenv("SMTP_USERNAME", "").strip() or None,
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip() or None,
        smtp_use_ssl=_parse_bool(os.getenv("SMTP_USE_SSL"), False),
        smtp_use_starttls=_parse_bool(os.getenv("SMTP_USE_STARTTLS"), False),
        smtp_from=os.getenv("SMTP_FROM", "memos-bot@localhost").strip(),
        smtp_to=os.getenv("SMTP_TO", "").strip() or None,
        smtp_timeout_seconds=int(os.getenv("SMTP_TIMEOUT_SECONDS", "20").strip()),
        empty_reminder_subject=os.getenv(
            "EMPTY_REMINDER_SUBJECT",
            "Memos 今日还没有记录，记得随手记一下",
        ).strip(),
        empty_reminder_body=os.getenv(
            "EMPTY_REMINDER_BODY",
            "今天的 Memos 还没有内容。你可以随手发一句话或一张照片，稍后系统会自动再尝试生成日报。",
        ).strip(),
        empty_reminder_once_per_day=_parse_bool(os.getenv("EMPTY_REMINDER_ONCE_PER_DAY"), True),
    )
