from __future__ import annotations

from utils.config import ConfigError, validate_runtime_environment


def main() -> None:
    try:
        summary = validate_runtime_environment(require_cookies=True)
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    print(
        "Configuration validation passed: "
        f"accounts={summary['accounts']}, targets={summary['targets']}, "
        f"match_mode={summary['match_mode']}, log_level={summary['log_level']}"
    )


if __name__ == "__main__":
    main()
