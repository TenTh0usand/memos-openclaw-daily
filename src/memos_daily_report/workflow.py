from __future__ import annotations

"""Small helpers for persisting workflow state.

OpenClaw 不需要理解 Python 内部对象，
只需要读取稳定的 JSON 状态文件，所以这里做最小状态层。
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
import json


@dataclass(slots=True)
class WorkflowState:
    """Persisted state shared across retries and external automation.

    持久化状态用于：
    - 避免同一天重复提醒
    - 让 OpenClaw 读取最新执行结果
    """
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
    """Read a previously persisted workflow state if it exists.

    如果状态文件存在，就把它读回来；否则返回空。
    """
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return WorkflowState(**data)


def write_state(path: Path, state: WorkflowState) -> None:
    """Write workflow state as UTF-8 JSON.

    统一用 UTF-8 JSON 落盘，方便人读也方便自动化读取。
    """
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
    """Create a new workflow state snapshot for the current run.

    基于本次执行结果创建状态快照。
    """
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
