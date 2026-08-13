import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

if os.path.exists(".env"):
    from dotenv import load_dotenv

    load_dotenv(".env")

from core.tasks import runTasks, smokeTasks

STATUS_FILE = Path("run-status.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_run_status(status: str, started_at: str, duration_seconds: float, mode: str, error_type: str = "") -> None:
    payload = {
        "status": status,
        "mode": mode,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": round(duration_seconds, 2),
    }
    if error_type:
        payload["error_type"] = error_type

    STATUS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    started_at = utc_now()
    started = time.monotonic()
    smoke = os.getenv("SPARKFLOW_SMOKE_TEST", "false").lower() in {"1", "true", "yes", "on"}
    mode = "smoke" if smoke else "send"

    try:
        if smoke:
            smokeTasks()
        else:
            runTasks()
    except Exception as exc:
        write_run_status(
            status="failure",
            started_at=started_at,
            duration_seconds=time.monotonic() - started,
            mode=mode,
            error_type=type(exc).__name__,
        )
        raise
    else:
        write_run_status(
            status="success",
            started_at=started_at,
            duration_seconds=time.monotonic() - started,
            mode=mode,
        )


if __name__ == "__main__":
    main()
