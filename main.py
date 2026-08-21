from __future__ import annotations

import argparse
from pathlib import Path

if Path(".env").exists():
    from dotenv import load_dotenv

    load_dotenv(".env")

from core.runtime import RunMode, execute_run, resolve_run_mode
from utils.config import validate_runtime_environment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SparkFlow unified runtime")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in RunMode],
        help="Run mode. Defaults to SPARKFLOW_MODE, legacy SPARKFLOW_SMOKE_TEST, then send.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and exit without opening a browser.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.validate:
        summary = validate_runtime_environment(require_cookies=True)
        print(
            "SparkFlow configuration valid: "
            f"{summary['accounts']} account(s), {summary['targets']} target(s), "
            f"match={summary['match_mode']}, log={summary['log_level']}"
        )
        return

    execute_run(resolve_run_mode(args.mode))


if __name__ == "__main__":
    main()
