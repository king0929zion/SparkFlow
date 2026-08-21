from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from utils.config import TRUTHY, validate_runtime_environment


class RunMode(str, Enum):
    SEND = "send"
    SMOKE = "smoke"


@dataclass(frozen=True)
class RunStatus:
    status: str
    mode: str
    started_at: str
    finished_at: str
    duration_seconds: float
    error_type: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_run_mode(explicit: str | None = None) -> RunMode:
    if explicit:
        return RunMode(explicit.strip().lower())

    configured = os.getenv("SPARKFLOW_MODE", "").strip().lower()
    if configured:
        try:
            return RunMode(configured)
        except ValueError as exc:
            raise ValueError("SPARKFLOW_MODE 仅支持 send 或 smoke") from exc

    legacy_smoke = os.getenv("SPARKFLOW_SMOKE_TEST", "").strip().lower()
    if legacy_smoke in TRUTHY:
        return RunMode.SMOKE
    return RunMode.SEND


def status_file() -> Path:
    return Path(os.getenv("SPARKFLOW_STATUS_FILE", "run-status.json"))


def write_run_status(status: RunStatus) -> None:
    payload = asdict(status)
    if not payload["error_type"]:
        payload.pop("error_type")
    status_file().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _task_for_mode(mode: RunMode) -> Callable[[], None]:
    from core.tasks import runTasks, smokeTasks

    return smokeTasks if mode is RunMode.SMOKE else runTasks


def execute_run(mode: RunMode) -> None:
    validate_runtime_environment(require_cookies=True)

    started_at = utc_now()
    started = time.monotonic()
    try:
        _task_for_mode(mode)()
    except Exception as exc:
        write_run_status(
            RunStatus(
                status="failure",
                mode=mode.value,
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.monotonic() - started, 2),
                error_type=type(exc).__name__,
            )
        )
        raise
    else:
        write_run_status(
            RunStatus(
                status="success",
                mode=mode.value,
                started_at=started_at,
                finished_at=utc_now(),
                duration_seconds=round(time.monotonic() - started, 2),
            )
        )
