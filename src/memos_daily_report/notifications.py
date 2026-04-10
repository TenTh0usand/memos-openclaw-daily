from __future__ import annotations

"""SMTP notification helpers.

只处理“怎么发提醒”，不关心“什么时候该提醒”。
提醒时机由 prepare 状态机决定。
"""

from email.message import EmailMessage
import smtplib

from memos_daily_report.config import Settings


class SmtpNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_enabled(self) -> bool:
        """A reminder can only be sent when both relay host and recipient exist.

        只有 SMTP 主机和收件地址都存在，提醒功能才算真正可用。
        """
        return bool(self.settings.smtp_host and self.settings.smtp_to)

    def send(self, *, subject: str, body: str) -> None:
        """Send one plain-text email through the configured relay.

        发送一封纯文本邮件，可用于对接 smtp-telegram 之类的桥接服务。
        """
        if not self.is_enabled:
            raise ValueError("SMTP is not fully configured. SMTP_HOST and SMTP_TO are required.")

        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = self.settings.smtp_to
        message["Subject"] = subject
        message.set_content(body)

        if self.settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as client:
                self._send_with_optional_auth(client, message)
            return

        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=self.settings.smtp_timeout_seconds,
        ) as client:
            if self.settings.smtp_use_starttls:
                client.starttls()
            self._send_with_optional_auth(client, message)

    def _send_with_optional_auth(self, client: smtplib.SMTP, message: EmailMessage) -> None:
        """Authenticate only when credentials are present.

        某些中继服务允许匿名发信，所以这里按需登录。
        """
        if self.settings.smtp_username:
            client.login(self.settings.smtp_username, self.settings.smtp_password or "")
        client.send_message(message)
