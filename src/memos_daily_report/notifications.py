from __future__ import annotations

from email.message import EmailMessage
import smtplib

from memos_daily_report.config import Settings


class SmtpNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_enabled(self) -> bool:
        return bool(self.settings.smtp_host and self.settings.smtp_to)

    def send(self, *, subject: str, body: str) -> None:
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
        if self.settings.smtp_username:
            client.login(self.settings.smtp_username, self.settings.smtp_password or "")
        client.send_message(message)
