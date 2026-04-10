from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class AttachmentRecord:
    name: str
    filename: str
    mime_type: str
    size: str | None
    external_link: str | None
    saved_path: str | None = None
    inline_content_base64: str | None = None
    download_error: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("inline_content_base64", None)
        data["inline_content_available"] = bool(self.inline_content_base64)
        return data


@dataclass(slots=True)
class MemoRecord:
    name: str
    create_time: str
    update_time: str | None
    display_time: str | None
    visibility: str
    pinned: bool
    tags: list[str] = field(default_factory=list)
    content: str = ""
    snippet: str | None = None
    attachments: list[AttachmentRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["attachments"] = [attachment.to_dict() for attachment in self.attachments]
        return data
