from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MESSAGE_TEMPLATE = "[盖瑞]今日火花[加一]\\n—— [右边] 每日一言 [左边] ——\\n[API]"
DEFAULT_HITOKOTO_TYPES = ("文学", "影视", "诗词", "哲学")
VALID_MATCH_MODES = {"nickname", "short_id"}
TRUTHY = {"1", "true", "yes", "on"}


class ConfigError(ValueError):
    """Raised when SparkFlow runtime configuration is invalid."""


class Environment(Enum):
    GITHUBACTION = "GITHUB_ACTION"
    LOCAL = "LOCAL"
    PACKED = "PACKED"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RuntimeConfig:
    proxy_address: str
    message_template: str
    hitokoto_types: tuple[str, ...]
    match_mode: str
    browser_timeout: int
    friend_list_timeout: int
    task_retry_times: int
    log_level: str

    def as_legacy_dict(self) -> dict[str, Any]:
        return {
            "proxyAddress": self.proxy_address,
            "messageTemplate": self.message_template,
            "hitokotoTypes": list(self.hitokoto_types),
            "matchMode": self.match_mode,
            "browserTimeout": self.browser_timeout,
            "friendListTimeout": self.friend_list_timeout,
            "taskRetryTimes": self.task_retry_times,
            "logLevel": self.log_level,
        }


@dataclass(frozen=True)
class AccountTask:
    unique_id: str
    username: str
    cookies: list[dict[str, Any]]
    targets: tuple[str, ...]

    def as_legacy_dict(self) -> dict[str, Any]:
        return {
            "unique_id": self.unique_id,
            "username": self.username,
            "cookies": self.cookies,
            "targets": list(self.targets),
        }


def get_environment() -> Environment:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Environment.PACKED
    if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
        return Environment.GITHUBACTION
    return Environment.LOCAL


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY


DEBUG = env_flag("SPARKFLOW_DEBUG", default=True)


def _read_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是整数，当前值: {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"{name} 必须大于 0，当前值: {value}")
    return value


def _read_json(name: str, default: str) -> Any:
    raw = os.getenv(name, default)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{name} 不是有效 JSON: {exc}") from exc


def load_runtime_config() -> RuntimeConfig:
    hitokoto_types = _read_json(
        "HITOKOTO_TYPES",
        json.dumps(DEFAULT_HITOKOTO_TYPES, ensure_ascii=False),
    )
    if not isinstance(hitokoto_types, list) or not hitokoto_types:
        raise ConfigError("HITOKOTO_TYPES 必须是非空 JSON 数组")
    normalized_types = tuple(
        str(item).strip() for item in hitokoto_types if str(item).strip()
    )
    if not normalized_types:
        raise ConfigError("HITOKOTO_TYPES 至少需要一个有效分类")

    match_mode = os.getenv("MATCH_MODE", "nickname").strip().lower()
    if match_mode not in VALID_MATCH_MODES:
        allowed = ", ".join(sorted(VALID_MATCH_MODES))
        raise ConfigError(f"MATCH_MODE 仅支持 {allowed}，当前值: {match_mode!r}")

    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    if log_level not in logging._nameToLevel:
        raise ConfigError(f"LOG_LEVEL 无效: {log_level!r}")

    return RuntimeConfig(
        proxy_address=os.getenv("PROXY_ADDRESS", "").strip(),
        message_template=os.getenv("MESSAGE_TEMPLATE", DEFAULT_MESSAGE_TEMPLATE),
        hitokoto_types=normalized_types,
        match_mode=match_mode,
        browser_timeout=_read_positive_int("BROWSER_TIMEOUT", 120000),
        friend_list_timeout=_read_positive_int("FRIEND_LIST_WAIT_TIME", 2000),
        task_retry_times=_read_positive_int("TASK_RETRY_TIMES", 3),
        log_level=log_level,
    )


def _normalize_same_site(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if raw in {"none", "no_restriction", "no-restriction"}:
        return "None"
    if raw == "strict":
        return "Strict"
    if raw == "lax":
        return "Lax"
    return None


def sanitize_cookies(cookies: Any) -> list[dict[str, Any]]:
    """Convert Cookie-Editor JSON into Playwright's cookie schema."""
    if not isinstance(cookies, list):
        raise ConfigError("Cookie 必须是 JSON 数组")

    normalized: list[dict[str, Any]] = []
    for index, cookie in enumerate(cookies, start=1):
        if not isinstance(cookie, dict):
            logger.warning("忽略第 %s 条非对象 Cookie", index)
            continue

        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "")
        domain = str(cookie.get("domain") or "").strip()
        url = str(cookie.get("url") or "").strip()
        path = str(cookie.get("path") or "/")

        if not name or (not domain and not url):
            logger.warning("忽略第 %s 条缺少 name 以及 domain/url 的 Cookie", index)
            continue

        item: dict[str, Any] = {
            "name": name,
            "value": value,
            "httpOnly": bool(cookie.get("httpOnly", False)),
            "secure": bool(cookie.get("secure", False)),
        }
        if url:
            item["url"] = url
        else:
            item["domain"] = domain
            item["path"] = path

        is_session = bool(cookie.get("session", False))
        expires = cookie.get("expires", cookie.get("expirationDate"))
        if not is_session and expires not in (None, ""):
            try:
                expires_value = float(expires)
                if expires_value > 1_000_000_000_000:
                    expires_value /= 1000
                if expires_value > 0:
                    item["expires"] = expires_value
            except (TypeError, ValueError):
                logger.debug("忽略第 %s 条 Cookie 的无效 expires", index)

        same_site = _normalize_same_site(cookie.get("sameSite"))
        if same_site:
            item["sameSite"] = same_site

        normalized.append(item)

    if not normalized:
        raise ConfigError("没有可用的 Cookie 条目")

    return normalized


def _load_cookie_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as first_error:
        try:
            decoded = raw.encode("utf-8").decode("unicode_escape")
            return json.loads(decoded)
        except Exception:
            raise ConfigError(f"Cookie JSON 无法解析: {first_error}") from first_error


def load_account_tasks(*, require_cookies: bool = True) -> list[AccountTask]:
    tasks = _read_json("TASKS", "[]")
    if not isinstance(tasks, list) or not tasks:
        raise ConfigError("TASKS 必须是非空 JSON 数组")

    accounts: list[AccountTask] = []
    seen_ids: set[str] = set()

    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise ConfigError(f"TASKS[{index}] 必须是对象")

        username = str(task.get("username") or "未知用户").strip() or "未知用户"
        unique_id = str(task.get("unique_id") or "").strip()
        if not unique_id:
            raise ConfigError(f"TASKS[{index}] 缺少 unique_id")

        normalized_id = unique_id.upper()
        if normalized_id in seen_ids:
            raise ConfigError(f"TASKS[{index}] 的 unique_id 重复: {unique_id}")
        seen_ids.add(normalized_id)

        raw_targets = task.get("targets")
        if not isinstance(raw_targets, list):
            raise ConfigError(f"TASKS[{index}].targets 必须是数组")
        targets = tuple(str(target).strip() for target in raw_targets if str(target).strip())
        if not targets:
            raise ConfigError(f"TASKS[{index}].targets 至少需要一个目标好友")

        cookies: list[dict[str, Any]] = []
        if require_cookies:
            cookies_key = f"COOKIES_{unique_id}".upper()
            cookies_raw = os.getenv(cookies_key, "")
            if not cookies_raw:
                raise ConfigError(f"{username} 缺少环境变量/Secret: {cookies_key}")
            cookies = sanitize_cookies(_load_cookie_json(cookies_raw))

        accounts.append(
            AccountTask(
                unique_id=unique_id,
                username=username,
                cookies=cookies,
                targets=targets,
            )
        )

    return accounts


def validate_runtime_environment(*, require_cookies: bool = True) -> dict[str, Any]:
    config = load_runtime_config()
    accounts = load_account_tasks(require_cookies=require_cookies)
    return {
        "accounts": len(accounts),
        "targets": sum(len(account.targets) for account in accounts),
        "match_mode": config.match_mode,
        "log_level": config.log_level,
    }


def get_config() -> dict[str, Any]:
    return load_runtime_config().as_legacy_dict()


def get_userData() -> list[dict[str, Any]]:
    return [account.as_legacy_dict() for account in load_account_tasks()]
