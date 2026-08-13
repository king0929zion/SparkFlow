import json
import logging
import os
import sys
from enum import Enum

from utils.logger import setup_logger

logger = setup_logger(level=logging.DEBUG)

DEBUG = True
config = None
userData = None


class Environment(Enum):
    GITHUBACTION = "GITHUB_ACTION"
    LOCAL = "LOCAL"
    PACKED = "PACKED"

    def __str__(self):
        return self.value


def get_environment():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Environment.PACKED
    if os.getenv("GITHUB_ACTIONS") == "true":
        return Environment.GITHUBACTION
    return Environment.LOCAL


def get_config():
    global config
    if config:
        return config

    config = {
        "proxyAddress": os.getenv("PROXY_ADDRESS", ""),
        "messageTemplate": os.getenv(
            "MESSAGE_TEMPLATE",
            "[盖瑞]今日火花[加一]\\n—— [右边] 每日一言 [左边] ——\\n[API]",
        ),
        "hitokotoTypes": json.loads(
            os.getenv("HITOKOTO_TYPES", '["文学","影视","诗词","哲学"]')
        ),
        "matchMode": os.getenv("MATCH_MODE", "nickname"),
        "browserTimeout": int(os.getenv("BROWSER_TIMEOUT", "120000")),
        "friendListTimeout": int(os.getenv("FRIEND_LIST_WAIT_TIME", "2000")),
        "taskRetryTimes": int(os.getenv("TASK_RETRY_TIMES", "3")),
        "logLevel": os.getenv("LOG_LEVEL", "DEBUG"),
    }
    return config


def _normalize_same_site(value):
    raw = str(value or "").strip().lower()
    if raw in {"none", "no_restriction", "no-restriction"}:
        return "None"
    if raw == "strict":
        return "Strict"
    if raw == "lax":
        return "Lax"
    return None


def sanitize_cookies(cookies):
    """Convert Cookie-Editor JSON into Playwright's cookie schema."""
    if not isinstance(cookies, list):
        raise ValueError("Cookie 必须是 JSON 数组")

    normalized = []
    for index, cookie in enumerate(cookies, start=1):
        if not isinstance(cookie, dict):
            logger.warning(f"忽略第 {index} 条非对象 Cookie")
            continue

        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        domain = str(cookie.get("domain") or "")
        path = str(cookie.get("path") or "/")
        if not name or not domain:
            logger.warning(f"忽略第 {index} 条缺少 name/domain 的 Cookie")
            continue

        item = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "httpOnly": bool(cookie.get("httpOnly", False)),
            "secure": bool(cookie.get("secure", False)),
        }

        is_session = bool(cookie.get("session", False))
        expires = cookie.get("expires", cookie.get("expirationDate"))
        if not is_session and expires not in (None, ""):
            try:
                expires_value = float(expires)
                if expires_value > 0:
                    item["expires"] = expires_value
            except (TypeError, ValueError):
                pass

        same_site = _normalize_same_site(cookie.get("sameSite"))
        if same_site:
            item["sameSite"] = same_site

        normalized.append(item)

    if not normalized:
        raise ValueError("没有可用的 Cookie 条目")

    return normalized


def _load_cookie_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as first_error:
        try:
            decoded = raw.encode("utf-8").decode("unicode_escape")
            return json.loads(decoded)
        except Exception:
            raise first_error


def get_userData():
    global userData
    if userData:
        return userData

    tasks = json.loads(os.getenv("TASKS", "[]"))
    userData = []

    for task in tasks:
        username = task.get("username", "未知用户")
        unique_id = task.get("unique_id")
        if not unique_id:
            logger.warning(f"{username} 的任务缺少 unique_id 字段，已跳过")
            continue

        cookies_key = f"COOKIES_{unique_id}".upper()
        cookies_str = os.getenv(cookies_key, "")
        if not cookies_str:
            logger.warning(f"{username} 的任务缺少 {cookies_key} 环境变量，已跳过")
            continue

        try:
            cookies = sanitize_cookies(_load_cookie_json(cookies_str))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"{username} 的任务 {cookies_key} 格式不正确，已跳过: {exc}")
            continue

        userData.append(
            {
                "unique_id": unique_id,
                "username": username,
                "cookies": cookies,
                "targets": task.get("targets", []),
            }
        )

    return userData
