import os
import re
import time
import traceback
import unicodedata
from pathlib import Path

from playwright.sync_api import Response, TimeoutError as PlaywrightTimeoutError

from core.browser import get_browser
from core.msg_builder import build_message
from utils.config import get_config, get_userData
from utils.logger import setup_logger

config = get_config()
userData = get_userData()
logger = setup_logger(level=config.get("logLevel", "Info"))
matchMode = config.get("matchMode", "nickname")

CHAT_URL = "https://www.douyin.com/chat"
CONVERSATION_ITEM = '[class*="conversationConversationItemwrapper"]'
CONVERSATION_TITLE = '[class*="conversationConversationItemtitle"]'
CONVERSATION_LIST = '[class*="conversationConversationListwrapper"]'
CHAT_EDITOR = '[class*="messageEditorimChatEditorContainer"]'
userIDDict = {}


def norm(value):
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.replace("\u3000", " ").replace("\xa0", " ")
    value = value.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", value).strip()


def handle_response(response: Response):
    """Collect identifiers from the Douyin Web IM user-info endpoint."""
    global userIDDict
    if "aweme/v1/web/im/user/info" not in response.url:
        return
    try:
        for item in response.json().get("data", []):
            nickname = norm(item.get("nickname"))
            remark = norm(item.get("remark_name") or nickname)
            ids = {
                norm(v)
                for v in (
                    item.get("short_id"),
                    item.get("unique_id"),
                    item.get("sec_uid"),
                    nickname,
                    remark,
                )
                if v not in (None, "")
            }
            for alias in {nickname, remark} - {""}:
                userIDDict[alias] = ids
    except Exception as exc:
        tb = traceback.extract_tb(exc.__traceback__)
        last = tb[-1] if tb else None
        where = f"{last.filename}:{last.lineno}" if last else "unknown"
        logger.warning(f"解析抖音好友信息失败 ({where}): {exc}")


def retry_operation(name, operation, retries=3, delay=2, *args, **kwargs):
    for attempt in range(retries):
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            if attempt >= retries - 1:
                logger.error(f"{name} 失败，已达到最大重试次数: {exc}")
                raise
            logger.warning(f"{name} 失败，{delay} 秒后重试: {exc}")
            time.sleep(delay)


def diagnose(page, username, reason):
    """Log non-sensitive state. Screenshot capture is opt-in because chat pages are private."""
    try:
        counts = (
            page.locator(CONVERSATION_LIST).count(),
            page.locator(CONVERSATION_ITEM).count(),
            page.locator(CHAT_EDITOR).count(),
        )
        title = page.title()
    except Exception:
        counts, title = (-1, -1, -1), "<unavailable>"
    logger.error(
        f"账号 {username} 页面诊断: reason={reason}; url={page.url}; title={title!r}; "
        f"lists={counts[0]}; items={counts[1]}; editors={counts[2]}"
    )
    if os.getenv("SAVE_FAILURE_SCREENSHOT", "false").lower() in {"1", "true", "yes", "on"}:
        try:
            Path("logs").mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
            page.screenshot(path=str(Path("logs") / f"{safe or 'account'}-chat-failure.png"))
        except Exception as exc:
            logger.warning(f"保存失败截图失败: {exc}")


def looks_logged_out(page):
    url = page.url.lower()
    if any(token in url for token in ("passport", "/login")):
        return True
    for text in ("扫码登录", "手机号登录", "验证码登录"):
        try:
            if page.get_by_text(text, exact=False).count() > 0:
                return True
        except Exception:
            pass
    return False


def ensure_chat_ready(page, username):
    timeout = min(config["browserTimeout"], 30000)
    try:
        page.locator(CONVERSATION_LIST).first.wait_for(state="visible", timeout=timeout)
        page.locator(CONVERSATION_ITEM).first.wait_for(state="visible", timeout=timeout)
    except PlaywrightTimeoutError as exc:
        diagnose(page, username, "chat-list-not-ready")
        if looks_logged_out(page):
            raise RuntimeError(
                "抖音 Web 登录态无效。请登录 https://www.douyin.com/chat 后重新导出 Cookie，"
                "再更新 COOKIES_<UNIQUE_ID>。"
            ) from exc
        raise RuntimeError(
            "抖音聊天列表未加载。可能是 Cookie 不适用于 www.douyin.com、账号没有私信会话，"
            "或抖音页面结构再次变化。"
        ) from exc


def resolve_target(display_name, targets):
    display = norm(display_name)
    target_map = {norm(target): str(target) for target in targets}
    if display in target_map:
        return target_map[display]
    for identifier in userIDDict.get(display, set()):
        if identifier in target_map:
            return target_map[identifier]
    return None


def scroll_and_select_user(page, username, targets):
    ensure_chat_ready(page, username)
    remaining = {str(target) for target in targets}
    seen = set()
    empty_rounds = 0
    scrollable = page.locator(CONVERSATION_LIST).first.element_handle()
    if not scrollable:
        raise RuntimeError("未找到可滚动的抖音会话列表")

    for round_no in range(1, 41):
        items = page.locator(CONVERSATION_ITEM)
        new_names = 0
        for index in range(items.count()):
            item = items.nth(index)
            try:
                display_name = norm(
                    item.locator(CONVERSATION_TITLE).first.inner_text(timeout=5000)
                )
            except Exception:
                continue
            if not display_name or display_name in seen:
                continue
            seen.add(display_name)
            new_names += 1
            target = resolve_target(display_name, remaining)
            if not target:
                continue
            item.click()
            remaining.discard(target)
            logger.info(f"账号 {username} 已匹配目标好友: {target}")
            yield target
            if not remaining:
                return
            break

        empty_rounds = 0 if new_names else empty_rounds + 1
        before = page.evaluate("el => el.scrollTop", scrollable)
        page.evaluate("el => { el.scrollTop += Math.max(640, el.clientHeight * 0.8); }", scrollable)
        time.sleep(0.45)
        after = page.evaluate("el => el.scrollTop", scrollable)
        if before == after:
            empty_rounds += 2
        logger.debug(
            f"账号 {username} 搜索 {round_no}/40, scroll={before}->{after}, "
            f"remaining={sorted(remaining)}, empty={empty_rounds}/10"
        )
        if empty_rounds >= 10:
            break
        time.sleep(0.7)

    diagnose(page, username, "targets-not-found")
    raise RuntimeError("未找到以下目标好友: " + ", ".join(sorted(remaining)))


def send_message(page, username, target):
    editor = page.locator(CHAT_EDITOR).first
    try:
        editor.wait_for(state="visible", timeout=config["browserTimeout"])
    except PlaywrightTimeoutError as exc:
        diagnose(page, username, f"editor-not-ready:{target}")
        raise RuntimeError(f"已找到好友 {target}，但聊天输入框未加载") from exc

    message = str(build_message() or "")
    if not message.strip():
        raise RuntimeError("消息模板生成结果为空，已取消发送")

    editor.click()
    lines = message.split("\\n")
    for index, line in enumerate(lines):
        editor.type(line)
        if index < len(lines) - 1:
            editor.press("Shift+Enter")
    editor.press("Enter")
    logger.info(f"账号 {username} 已向目标 {target} 提交消息")
    time.sleep(2)


def do_user_task(browser, username, cookies, targets):
    global userIDDict
    userIDDict = {}
    context = browser.new_context()
    context.set_default_navigation_timeout(config["browserTimeout"])
    context.set_default_timeout(config["browserTimeout"])
    try:
        context.add_cookies(cookies)
        if not context.cookies([CHAT_URL]):
            raise RuntimeError(
                "当前 Cookie 没有任何条目可用于 www.douyin.com。"
                "请登录 https://www.douyin.com/chat 后重新导出 Cookie。"
            )

        page = context.new_page()
        page.on("response", handle_response)
        retry_operation(
            "打开抖音 Web 聊天页面",
            page.goto,
            retries=config["taskRetryTimes"],
            delay=5,
            url=CHAT_URL,
            wait_until="domcontentloaded",
        )
        time.sleep(min(5, max(2, config["friendListTimeout"] / 1000)))
        ensure_chat_ready(page, username)

        sent = []
        for target in scroll_and_select_user(page, username, targets):
            send_message(page, username, target)
            sent.append(target)

        expected = {str(target) for target in targets}
        if set(sent) != expected:
            raise RuntimeError("部分目标未完成发送: " + ", ".join(sorted(expected - set(sent))))
        logger.info(f"账号 {username} 已完成 {len(sent)} 个目标好友消息任务")
    finally:
        context.close()


def runTasks():
    if not userData:
        raise RuntimeError("没有可执行账号，请检查 TASKS 与 COOKIES_<UNIQUE_ID>")
    playwright, browser = get_browser()
    if not playwright or not browser:
        raise RuntimeError("Playwright 浏览器启动失败")
    try:
        logger.info("开始执行任务")
        for user in userData:
            username = user.get("username", "未知用户")
            logger.info(f"开始处理账号 {username}")
            do_user_task(browser, username, user["cookies"], user["targets"])
            logger.info(f"账号 {username} 任务完成")
    finally:
        browser.close()
        playwright.stop()
