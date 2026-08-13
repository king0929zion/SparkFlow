import json
import os
import re
import sys
import uuid

ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def as_env_string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def make_delimiter(value: str) -> str:
    while True:
        delimiter = f"SPARKFLOW_ENV_{uuid.uuid4().hex}"
        if delimiter not in value:
            return delimiter


def append_github_env_block(env_file, key: str, value: str) -> None:
    if not ENV_KEY_RE.fullmatch(key):
        fail(f"Invalid environment variable name: {key}")

    delimiter = make_delimiter(value)
    env_file.write(f"{key}<<{delimiter}\n")
    env_file.write(value)
    if value and not value.endswith("\n"):
        env_file.write("\n")
    env_file.write(f"{delimiter}\n")


def load_json_object(raw: str, label: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"{label} is not valid JSON: {exc}")

    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def main() -> None:
    github_env = os.getenv("GITHUB_ENV")
    if not github_env:
        fail("GITHUB_ENV is not set")

    vars_map = load_json_object(os.getenv("VARS_JSON", "{}"), "VARS_JSON")
    secrets_map = load_json_object(os.getenv("SECRETS_JSON", "{}"), "SECRETS_JSON")

    # Secrets intentionally override repository variables with the same key.
    merged = {**vars_map, **secrets_map}

    with open(github_env, "a", encoding="utf-8") as env_file:
        for raw_key, raw_value in merged.items():
            key = str(raw_key)
            append_github_env_block(env_file, key, as_env_string(raw_value))

    # Do not persist secrets to a workspace .env file in GitHub Actions.
    print(
        f"Exported {len(vars_map)} repository variable(s) and "
        f"{len(secrets_map)} secret(s) to GITHUB_ENV."
    )


if __name__ == "__main__":
    main()
