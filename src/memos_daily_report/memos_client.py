from __future__ import annotations

from base64 import b64decode
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
import mimetypes
import re

import requests

from memos_daily_report.models import AttachmentRecord, MemoRecord


def _safe_stem(value: str) -> str:
    collapsed = re.sub(r"[^0-9A-Za-z._-]+", "-", value.strip())
    return collapsed.strip("-._") or "attachment"


class MemosClient:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "memos-openclaw-daily/0.1.0",
            }
        )
        self.verify_ssl = verify_ssl

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        stream: bool = False,
        timeout: int = 60,
    ) -> requests.Response:
        response = self.session.request(
            method=method,
            url=f"{self.base_url}{path}",
            params=params,
            json=json_body,
            stream=stream,
            timeout=timeout,
            verify=self.verify_ssl,
        )
        response.raise_for_status()
        return response

    def list_memos_for_day(
        self,
        *,
        target_date: date,
        timezone_name: str,
        time_field: str = "created_ts",
        page_size: int = 200,
    ) -> list[MemoRecord]:
        if time_field not in {"created_ts", "updated_ts"}:
            raise ValueError("time_field must be created_ts or updated_ts.")

        timezone = ZoneInfo(timezone_name)
        start_local = datetime.combine(target_date, time.min, tzinfo=timezone)
        end_local = start_local + timedelta(days=1)
        start_ts = int(start_local.timestamp())
        end_ts = int(end_local.timestamp())
        filter_expression = f"{time_field} >= {start_ts} && {time_field} < {end_ts}"

        memos: list[MemoRecord] = []
        next_page_token = ""

        while True:
            response = self._request(
                "GET",
                "/api/v1/memos",
                params={
                    "pageSize": min(page_size, 1000),
                    "pageToken": next_page_token,
                    "state": "NORMAL",
                    "orderBy": "create_time asc",
                    "filter": filter_expression,
                },
            )
            payload = response.json()
            for raw_memo in payload.get("memos", []):
                memos.append(self._convert_memo(raw_memo))
            next_page_token = payload.get("nextPageToken", "")
            if not next_page_token:
                break

        return memos

    def create_memo(
        self,
        *,
        content: str,
        visibility: str = "PRIVATE",
        display_time: datetime | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "state": "NORMAL",
            "content": content,
            "visibility": visibility,
        }
        if display_time is not None:
            body["displayTime"] = display_time.astimezone().isoformat()

        response = self._request("POST", "/api/v1/memos", json_body=body)
        return response.json()

    def _convert_memo(self, raw_memo: dict[str, Any]) -> MemoRecord:
        attachments = [self._convert_attachment(item) for item in raw_memo.get("attachments", [])]
        return MemoRecord(
            name=raw_memo["name"],
            create_time=raw_memo.get("createTime", ""),
            update_time=raw_memo.get("updateTime"),
            display_time=raw_memo.get("displayTime"),
            visibility=raw_memo.get("visibility", "PRIVATE"),
            pinned=bool(raw_memo.get("pinned", False)),
            tags=list(raw_memo.get("tags", [])),
            content=raw_memo.get("content", ""),
            snippet=raw_memo.get("snippet"),
            attachments=attachments,
        )

    def _convert_attachment(self, raw_attachment: dict[str, Any]) -> AttachmentRecord:
        return AttachmentRecord(
            name=raw_attachment.get("name", ""),
            filename=raw_attachment.get("filename") or "attachment",
            mime_type=raw_attachment.get("type") or "application/octet-stream",
            size=raw_attachment.get("size"),
            external_link=raw_attachment.get("externalLink"),
            inline_content_base64=raw_attachment.get("content"),
        )

    def download_attachment(
        self,
        *,
        attachment: AttachmentRecord,
        destination_dir: Path,
        index: int,
        memo_name: str,
    ) -> AttachmentRecord:
        filename = self._build_filename(
            index=index,
            memo_name=memo_name,
            original_name=attachment.filename,
            mime_type=attachment.mime_type,
        )
        destination_path = destination_dir / filename

        try:
            payload_bytes = self._resolve_attachment_bytes(attachment)
            destination_path.write_bytes(payload_bytes)
            attachment.saved_path = str(destination_path.resolve())
        except Exception as exc:  # noqa: BLE001
            attachment.download_error = str(exc)

        return attachment

    def _resolve_attachment_bytes(self, attachment: AttachmentRecord) -> bytes:
        if attachment.external_link:
            url = self._absolute_url(attachment.external_link)
            headers = None
            if self._same_origin(url):
                headers = {"Authorization": self.session.headers["Authorization"]}
            response = requests.get(url, headers=headers, timeout=120, verify=self.verify_ssl)
            response.raise_for_status()
            return response.content

        if attachment.inline_content_base64:
            return b64decode(attachment.inline_content_base64)

        if attachment.name and attachment.filename:
            file_url = f"{self.base_url}/file/{attachment.name}/{attachment.filename}"
            response = requests.get(
                file_url,
                headers={"Authorization": self.session.headers["Authorization"]},
                timeout=120,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            return response.content

        raise ValueError("Attachment has neither externalLink, inline content, nor file route fallback.")

    def _absolute_url(self, maybe_relative_url: str) -> str:
        parsed = urlparse(maybe_relative_url)
        if parsed.scheme and parsed.netloc:
            return maybe_relative_url
        return urljoin(f"{self.base_url}/", maybe_relative_url.lstrip("/"))

    def _same_origin(self, url: str) -> bool:
        return urlparse(url).netloc == urlparse(self.base_url).netloc

    def _build_filename(self, *, index: int, memo_name: str, original_name: str, mime_type: str) -> str:
        stem = Path(original_name).stem or "attachment"
        suffix = Path(original_name).suffix
        if not suffix:
            suffix = mimetypes.guess_extension(mime_type) or ""
        memo_fragment = memo_name.split("/", 1)[-1]
        return f"{index:03d}_{_safe_stem(memo_fragment)}_{_safe_stem(stem)}{suffix}"
