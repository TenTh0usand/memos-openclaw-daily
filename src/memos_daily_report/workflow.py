from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
import json


@dataclass(slots=True)
class WorkflowState:
    date: str
    run_dir: str
    memo_count: int
    status: str
    context_path: str
    memos_json_path: str
    reminder_sent: bool = False
    reminder_sent_at: str | None = None
    reminder_error: str | None = None
    forced: bool = False
    checked_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def read_state(path: Path) -> WorkflowState | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return WorkflowState(**data)


def write_state(path: Path, state: WorkflowState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def build_state(
    *,
    target_date: date,
    run_dir: Path,
    context_path: Path,
    memos_json_path: Path,
    memo_count: int,
    status: str,
    forced: bool,
    reminder_sent: bool = False,
    reminder_sent_at: str | None = None,
    reminder_error: str | None = None,
) -> WorkflowState:
    return WorkflowState(
        date=target_date.isoformat(),
        run_dir=str(run_dir.resolve()),
        memo_count=memo_count,
        status=status,
        context_path=str(context_path.resolve()),
        memos_json_path=str(memos_json_path.resolve()),
        reminder_sent=reminder_sent,
        reminder_sent_at=reminder_sent_at,
        reminder_error=reminder_error,
        forced=forced,
        checked_at=datetime.now().astimezone().isoformat(),
    )
