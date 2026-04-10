from __future__ import annotations

"""CLI entrypoints for the Memos daily-report workflow.

命令行入口负责把几个阶段串起来：
1. collect: 收集当天 memo 与附件
2. prepare: 收集并判断是否该继续生成日报
3. publish: 把生成好的日报写回 Memos
4. send-reminder: 手动发送 SMTP 提醒
"""

from argparse import ArgumentParser, Namespace
from datetime import date, datetime
from pathlib import Path
import json
import sys
from zoneinfo import ZoneInfo

from memos_daily_report.config import Settings, load_settings
from memos_daily_report.memos_client import MemosClient
from memos_daily_report.models import AttachmentRecord, MemoRecord
from memos_daily_report.notifications import SmtpNotifier
from memos_daily_report.workflow import build_state, read_state, write_state


def build_parser() -> ArgumentParser:
    """Build the public CLI surface.

    构建对外暴露的命令行参数结构。
    """
    parser = ArgumentParser(description="Collect daily Memos content for OpenClaw and publish reports back to Memos.")
    parser.add_argument("--env-file", help="Optional path to a .env file.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect one day's memos and attachments.")
    collect_parser.add_argument("--date", dest="target_date", help="Target date in YYYY-MM-DD. Defaults to today in MEMOS_TIMEZONE.")
    collect_parser.add_argument(
        "--time-field",
        choices=["created_ts", "updated_ts"],
        default="created_ts",
        help="Which Memos timestamp filter to use.",
    )
    collect_parser.add_argument("--output-root", help="Override MEMOS_OUTPUT_ROOT for this run.")
    collect_parser.add_argument(
        "--download-attachments",
        dest="download_attachments",
        action="store_true",
        default=True,
        help="Download attachment files into the media directory.",
    )
    collect_parser.add_argument(
        "--no-download-attachments",
        dest="download_attachments",
        action="store_false",
        help="Skip downloading attachment files.",
    )

    publish_parser = subparsers.add_parser("publish", help="Publish a generated report back to Memos.")
    publish_parser.add_argument("--content-file", help="Markdown file to publish.")
    publish_parser.add_argument("--content", help="Literal Markdown content to publish.")
    publish_parser.add_argument("--visibility", help="Override MEMOS_REPORT_VISIBILITY.")
    publish_parser.add_argument("--tag", help="Override MEMOS_REPORT_TAG.")
    publish_parser.add_argument("--display-date", help="Use YYYY-MM-DD as the report display date.")

    prepare_parser = subparsers.add_parser("prepare", help="Collect memos and decide whether OpenClaw should generate a report now.")
    prepare_parser.add_argument("--date", dest="target_date", help="Target date in YYYY-MM-DD. Defaults to today in MEMOS_TIMEZONE.")
    prepare_parser.add_argument(
        "--time-field",
        choices=["created_ts", "updated_ts"],
        default="created_ts",
        help="Which Memos timestamp filter to use.",
    )
    prepare_parser.add_argument("--output-root", help="Override MEMOS_OUTPUT_ROOT for this run.")
    prepare_parser.add_argument(
        "--download-attachments",
        dest="download_attachments",
        action="store_true",
        default=True,
        help="Download attachment files into the media directory.",
    )
    prepare_parser.add_argument(
        "--no-download-attachments",
        dest="download_attachments",
        action="store_false",
        help="Skip downloading attachment files.",
    )
    prepare_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow downstream report generation even when memoCount is 0.",
    )
    prepare_parser.add_argument(
        "--send-empty-reminder",
        dest="send_empty_reminder",
        action="store_true",
        default=True,
        help="Send SMTP reminder if memoCount is 0 and SMTP is configured.",
    )
    prepare_parser.add_argument(
        "--no-send-empty-reminder",
        dest="send_empty_reminder",
        action="store_false",
        help="Do not send SMTP reminder even when memoCount is 0.",
    )

    remind_parser = subparsers.add_parser("send-reminder", help="Send a manual SMTP reminder.")
    remind_parser.add_argument("--subject", help="Override SMTP reminder subject.")
    remind_parser.add_argument("--body", help="Override SMTP reminder body.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch subcommands and convert runtime errors into CLI-friendly output.

    统一分发子命令，并把运行时异常转成更容易看懂的命令行错误信息。
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings(args.env_file)

    try:
        if args.command == "collect":
            return _run_collect(args, settings)
        if args.command == "publish":
            return _run_publish(args, settings)
        if args.command == "prepare":
            return _run_prepare(args, settings)
        if args.command == "send-reminder":
            return _run_send_reminder(args, settings)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error("Unknown command.")
    return 2


def _run_collect(args: Namespace, settings: Settings) -> int:
    """Collect one day of memos and write derived artifacts to disk.

    收集某一天的 memo，并把上下文文件与状态文件写入输出目录。
    """
    collection = _collect_day(
        args=args,
        settings=settings,
    )
    # latest.txt gives OpenClaw a stable pointer to the newest run directory.
    # latest.txt 让 OpenClaw 可以稳定定位到“最近一次运行目录”。
    latest_path = collection["output_root"] / "latest.txt"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(str(collection["run_dir"].resolve()), encoding="utf-8")
    latest_status_path = collection["output_root"] / "latest_status.json"
    state = build_state(
        target_date=collection["target_date"],
        run_dir=collection["run_dir"],
        context_path=collection["context_path"],
        memos_json_path=collection["json_path"],
        memo_count=len(collection["memos"]),
        status="ready" if collection["memos"] else "empty",
        forced=False,
    )
    write_state(latest_status_path, state)
    print(str(collection["context_path"].resolve()))
    return 0


def _run_publish(args: Namespace, settings: Settings) -> int:
    """Publish a generated Markdown report back to Memos.

    把已经生成好的 Markdown 日报回写成一条新的 Memos 记录。
    """
    content = _load_publish_content(args)
    tag = (args.tag or settings.report_tag).strip().lstrip("#")
    if tag and f"#{tag}" not in content:
        content = f"{content.rstrip()}\n\n#{tag}\n"

    display_time = None
    if args.display_date:
        timezone = ZoneInfo(settings.timezone)
        target_date = datetime.strptime(args.display_date, "%Y-%m-%d").date()
        display_time = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone)

    client = MemosClient(settings.memos_base_url, settings.memos_token, verify_ssl=settings.verify_ssl)
    response = client.create_memo(
        content=content,
        visibility=(args.visibility or settings.report_visibility).upper(),
        display_time=display_time,
    )
    print(response.get("name", ""))
    return 0


def _run_prepare(args: Namespace, settings: Settings) -> int:
    """Collect context and decide whether downstream summarization should continue.

    这是状态机入口：既收集数据，也决定现在是否应该继续生成日报。
    """
    collection = _collect_day(args=args, settings=settings)
    output_root = collection["output_root"]
    run_dir = collection["run_dir"]
    target_date = collection["target_date"]
    memo_count = len(collection["memos"])
    state_path = run_dir / "workflow_state.json"
    latest_status_path = output_root / "latest_status.json"
    latest_path = output_root / "latest.txt"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(str(run_dir.resolve()), encoding="utf-8")

    prior_state = read_state(state_path)
    reminder_sent = bool(prior_state and prior_state.reminder_sent)
    reminder_sent_at = prior_state.reminder_sent_at if prior_state else None
    reminder_error = None

    # The status is the handoff contract between Python and OpenClaw.
    # 这个 status 就是 Python 和 OpenClaw 之间的“交接协议”。
    if memo_count > 0:
        status = "ready"
    elif args.force:
        status = "forced_ready"
    else:
        status = "waiting_retry"
        if args.send_empty_reminder:
            notifier = SmtpNotifier(settings)
            should_send = notifier.is_enabled and (
                not settings.empty_reminder_once_per_day or not (prior_state and prior_state.reminder_sent)
            )
            if should_send:
                try:
                    notifier.send(
                        subject=settings.empty_reminder_subject,
                        body=settings.empty_reminder_body,
                    )
                    reminder_sent = True
                    reminder_sent_at = datetime.now().astimezone().isoformat()
                except Exception as exc:  # noqa: BLE001
                    reminder_error = str(exc)
            elif prior_state and prior_state.reminder_sent:
                reminder_sent = True

    state = build_state(
        target_date=target_date,
        run_dir=run_dir,
        context_path=collection["context_path"],
        memos_json_path=collection["json_path"],
        memo_count=memo_count,
        status=status,
        forced=bool(args.force),
        reminder_sent=reminder_sent,
        reminder_sent_at=reminder_sent_at,
        reminder_error=reminder_error,
    )
    write_state(state_path, state)
    write_state(latest_status_path, state)
    print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _run_send_reminder(args: Namespace, settings: Settings) -> int:
    """Send an SMTP reminder directly from the CLI.

    允许你在不跑完整工作流的情况下单独发送一条提醒。
    """
    notifier = SmtpNotifier(settings)
    notifier.send(
        subject=(args.subject or settings.empty_reminder_subject),
        body=(args.body or settings.empty_reminder_body),
    )
    print("sent")
    return 0


def _parse_date_or_today(raw_date: str | None, timezone: ZoneInfo) -> date:
    """Parse an explicit date or fall back to today's date in the configured timezone.

    优先使用显式传入的日期，否则回落到配置时区下的“今天”。
    """
    if raw_date:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    return datetime.now(timezone).date()


def _load_publish_content(args: Namespace) -> str:
    """Load report content from a file, literal argument, or stdin.

    支持三种输入来源：文件、直接参数、标准输入。
    """
    if args.content_file:
        return Path(args.content_file).read_text(encoding="utf-8")
    if args.content:
        return args.content
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise ValueError("Provide --content-file, --content, or stdin for publish.")


def _collect_day(args: Namespace, settings: Settings) -> dict:
    """Collect the canonical daily payload consumed by OpenClaw.

    这是整个项目的核心收集器：统一输出 JSON、Markdown 和本地图片目录。
    """
    timezone = ZoneInfo(settings.timezone)
    target_date = _parse_date_or_today(getattr(args, "target_date", None), timezone)
    output_root = Path(args.output_root).expanduser() if getattr(args, "output_root", None) else settings.output_root
    run_dir = output_root / target_date.isoformat()
    media_dir = run_dir / "media"
    run_dir.mkdir(parents=True, exist_ok=True)
    if getattr(args, "download_attachments", True):
        media_dir.mkdir(parents=True, exist_ok=True)

    client = MemosClient(settings.memos_base_url, settings.memos_token, verify_ssl=settings.verify_ssl)
    memos = client.list_memos_for_day(
        target_date=target_date,
        timezone_name=settings.timezone,
        time_field=args.time_field,
    )

    # Keep attachment filenames deterministic so later prompts can reference them reliably.
    # 让附件文件名保持稳定，后续 prompt 引用图片时会更可靠。
    attachment_index = 1
    collected_memos: list[MemoRecord] = []
    for memo in memos:
        collected_attachments: list[AttachmentRecord] = []
        for attachment in memo.attachments:
            if getattr(args, "download_attachments", True):
                downloaded = client.download_attachment(
                    attachment=attachment,
                    destination_dir=media_dir,
                    index=attachment_index,
                    memo_name=memo.name,
                )
            else:
                downloaded = attachment
            collected_attachments.append(downloaded)
            attachment_index += 1
        memo.attachments = collected_attachments
        collected_memos.append(memo)

    json_path = run_dir / "memos.json"
    json_path.write_text(
        json.dumps(
            {
                "date": target_date.isoformat(),
                "timezone": settings.timezone,
                "memoCount": len(collected_memos),
                "memos": [memo.to_dict() for memo in collected_memos],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    context_path = run_dir / "daily_context.md"
    context_path.write_text(_render_context_markdown(target_date, settings.timezone, collected_memos), encoding="utf-8")
    return {
        "target_date": target_date,
        "output_root": output_root,
        "run_dir": run_dir,
        "json_path": json_path,
        "context_path": context_path,
        "memos": collected_memos,
    }


def _render_context_markdown(target_date: date, timezone_name: str, memos: list[MemoRecord]) -> str:
    """Render a human-readable but model-friendly Markdown context file.

    这个 Markdown 既给人看，也给 OpenClaw 看，所以会保留足够多的原始细节。
    """
    lines: list[str] = [
        f"# {target_date.isoformat()} Memos Daily Context",
        "",
        f"- 时区: `{timezone_name}`",
        f"- memo 数量: `{len(memos)}`",
        "- 说明: 这是给 OpenClaw 读取的原始上下文，请结合图片一起理解，不要编造。",
        "",
    ]

    if not memos:
        lines.extend(
            [
                "## 今日无记录",
                "",
                "今天在所选时间范围内没有查到 memo。",
                "",
            ]
        )
        return "\n".join(lines)

    for index, memo in enumerate(memos, start=1):
        lines.extend(
            [
                f"## {index}. {memo.name}",
                "",
                f"- 创建时间: `{memo.create_time}`",
                f"- 更新时间: `{memo.update_time or 'N/A'}`",
                f"- 展示时间: `{memo.display_time or 'N/A'}`",
                f"- 可见性: `{memo.visibility}`",
                f"- 置顶: `{memo.pinned}`",
                f"- 标签: `{', '.join(memo.tags) if memo.tags else '无'}`",
                "",
                "### 内容",
                "",
                memo.content.strip() or "（空内容）",
                "",
            ]
        )

        if memo.attachments:
            lines.extend(["### 附件", ""])
            for attachment in memo.attachments:
                attachment_lines = [
                    f"- 文件: `{attachment.filename}`",
                    f"  - 类型: `{attachment.mime_type}`",
                ]
                if attachment.saved_path:
                    attachment_lines.append(f"  - 本地路径: `{attachment.saved_path}`")
                if attachment.external_link:
                    attachment_lines.append(f"  - 原始链接: `{attachment.external_link}`")
                if attachment.download_error:
                    attachment_lines.append(f"  - 下载错误: `{attachment.download_error}`")
                lines.extend(attachment_lines)
            lines.append("")
        else:
            lines.extend(["### 附件", "", "无附件", ""])

    return "\n".join(lines)
