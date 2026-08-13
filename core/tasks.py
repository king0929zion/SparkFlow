import os
import re
import time
import unicodedata
from pathlib import Path

from playwright.sync_api import Response

from core.browser import get_browser
from core.msg_builder import build_message
from utils.config import get_config, get_userData
from utils.logger import setup_logger

config = get_config()
userData = get_userData()
logger = setup_logger(level=config.get("logLevel", "Info"))
matchMode = config.get("matchMode", "nickname")

CHAT_URL = "https://www.douyin.com/chat"
SEARCH_SELECTORS = (
    'input.semi-input[placeholder="搜索"][type="text"]',
    'input.semi-input[placeholder="搜索"]',
    'input[placeholder="搜索"]',
    '.searchSearchInputinput_box input',
    '.LeftPanelHeadersearch input',
)
CHAT_BUTTON_SELECTORS = (
    'div[class*="SearchPanelitemchat_btn"]',
    '[class*="chat_btn"]',
    '[class*="SearchPanel"] [class*="btn"]',
    '.semi-button',
)
CHAT_EDITOR_SELECTORS = (
    '.messageEditorimChatEditorContainer [data-slate-editor="true"][contenteditable="true"]',
    'div[data-slate-editor="true"][contenteditable="true"]',
    '[class*="messageEditorimChatEditorContainer"] [contenteditable="true"]',
    '[contenteditable="true"][role="textbox"]',
)
CONVERSATION_LIST_SELECTORS = (
    '.conversationConversationListwrapper',
    '[class*="conversationConversationListwrapper"]',
)
CONVERSATION_ITEM_SELECTORS = (
    '.conversationConversationItemwrapper',
    '[class*="conversationConversationItemwrapper"]',
)
CONVERSATION_TITLE_SELECTORS = (
    '.conversationConversationItemtitle',
    '[class*="conversationConversationItemtitle"]',
)
LOGIN_TEXTS = ("扫码登录", "手机号登录", "验证码登录")
AUTH_COOKIE_MARKERS = (
    "sessionid",
    "sessionid_ss",
    "sid_guard",
    "sid_tt",
    "uid_tt",
    "uid_tt_ss",
)

userIDDict = {}


def norm(value):
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.replace("\u3000", " ").replace("\xa0", " ")
    value = value.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", value).strip()


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


def handle_response(response: Response):
    """Collect Douyin Web IM user metadata used for short_id matching."""
    if "aweme/v1/web/im/user/info" not in response.url:
        return
    if response.status >= 400:
        logger.debug(f"好友信息接口状态异常: {response.status}")
        return

    try:
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(data, list):
            return

        added = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            nickname = norm(item.get("nickname"))
            remark_name = norm(item.get("remark_name"))
            display_name = remark_name or nickname
            if not display_name:
                continue

            for key in ("short_id", "unique_id", "sec_uid"):
                identifier = norm(item.get(key))
                if identifier:
                    if userIDDict.get(identifier) != display_name:
                        userIDDict[identifier] = display_name
                        added += 1

        if added:
            logger.debug(f"好友信息映射新增 {added} 项，当前共 {len(userIDDict)} 项")
    except Exception as exc:
        logger.debug(f"解析好友信息接口失败: {exc}")


def first_visible(page, selectors):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                return locator, selector
        except Exception:
            continue
    return None, ""


def wait_for_any_visible(page, selectors, timeout_ms):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        locator, selector = first_visible(page, selectors)
        if locator is not None:
            return locator, selector
        time.sleep(0.25)
    return None, ""


def looks_logged_out(page):
    url = page.url.lower()
    if any(token in url for token in ("passport", "/login")):
        return True
    for text in LOGIN_TEXTS:
        try:
            matches = page.get_by_text(text, exact=False)
            for index in range(min(matches.count(), 8)):
                if matches.nth(index).is_visible():
                    return True
        except Exception:
            continue
    return False


def diagnose(page, username, reason):
    try:
        title = page.title()
        html_len = len(page.content())
        search_count = sum(page.locator(sel).count() for sel in SEARCH_SELECTORS)
        list_count = sum(page.locator(sel).count() for sel in CONVERSATION_LIST_SELECTORS)
        editor_count = sum(page.locator(sel).count() for sel in CHAT_EDITOR_SELECTORS)
        mapped_ids = len(userIDDict)
        login_visible = looks_logged_out(page)
    except Exception:
        title = "<unavailable>"
        html_len = search_count = list_count = editor_count = mapped_ids = -1
        login_visible = False

    logger.error(
        f"账号 {username} 页面诊断: reason={reason}; url={page.url}; title={title!r}; "
        f"html_len={html_len}; search={search_count}; lists={list_count}; "
        f"editors={editor_count}; mapped_ids={mapped_ids}; login_visible={login_visible}"
    )

    if os.getenv("SAVE_FAILURE_SCREENSHOT", "false").lower() in {"1", "true", "yes", "on"}:
        try:
            Path("logs").mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
            page.screenshot(
                path=str(Path("logs") / f"{safe or 'account'}-chat-failure.png"),
                full_page=False,
            )
        except Exception as exc:
            logger.warning(f"保存失败截图失败: {exc}")


def create_context(browser):
    context = browser.new_context()
    context.set_default_navigation_timeout(config["browserTimeout"])
    context.set_default_timeout(config["browserTimeout"])
    return context


def open_chat_page(browser, username, cookies):
    userIDDict.clear()
    context = create_context(browser)
    try:
        context.add_cookies(cookies)
        scoped_cookies = context.cookies([CHAT_URL])
        if not scoped_cookies:
            raise RuntimeError(
                "当前 Cookie 没有任何条目可用于 www.douyin.com。"
                "请从 https://www.douyin.com/chat 重新导出 Cookie。"
            )

        domains = sorted(
            {cookie.get("domain", "") for cookie in scoped_cookies if cookie.get("domain")}
        )
        cookie_names = {cookie.get("name", "") for cookie in scoped_cookies}
        auth_markers = [name for name in AUTH_COOKIE_MARKERS if name in cookie_names]
        logger.info(
            f"账号 {username} 已载入 {len(scoped_cookies)} 条 Web Cookie，"
            f"域名数 {len(domains)}，认证标记 {auth_markers or ['未识别']}"
        )

        page = context.new_page()
        page.on("response", handle_response)

        response = retry_operation(
            "打开抖音 Web 聊天页面",
            page.goto,
            retries=config["taskRetryTimes"],
            delay=4,
            url=CHAT_URL,
            wait_until="domcontentloaded",
            timeout=min(config["browserTimeout"], 60000),
        )
        if response is not None:
            logger.info(
                f"账号 {username} 聊天页导航状态: HTTP {response.status}; final_url={page.url}"
            )

        page.wait_for_timeout(10000)
        return context, page
    except Exception:
        context.close()
        raise


def ensure_chat_ready(page, username):
    timeout = min(config["browserTimeout"], 30000)
    ready_selectors = SEARCH_SELECTORS + CONVERSATION_LIST_SELECTORS
    locator, selector = wait_for_any_visible(page, ready_selectors, timeout)
    if locator is not None:
        logger.info(f"账号 {username} Web Chat 已就绪: {selector}")
        return locator

    diagnose(page, username, "chat-shell-not-ready")
    if looks_logged_out(page):
        raise RuntimeError(
            "抖音 Web Chat 显示可见登录界面。Cookie 已注入，但抖音没有接受当前会话；"
            "请查看日志中的认证标记。如果认证 Cookie 存在仍被要求登录，通常是验证码/风控而不是配置 JSON 错误。"
        )
    raise RuntimeError(
        "抖音 Web Chat 外壳未加载，请查看本次 smoke 诊断中的 HTTP 状态和 DOM 计数。"
    )


def get_search_input(page, username):
    ensure_chat_ready(page, username)
    search_input, selector = wait_for_any_visible(page, SEARCH_SELECTORS, 10000)
    if search_input is None:
        diagnose(page, username, "search-input-not-found")
        raise RuntimeError("抖音 Web Chat 已加载，但未找到可见搜索框")
    logger.debug(f"账号 {username} 使用搜索框选择器: {selector}")
    return search_input


def find_chat_button(page, target, timeout_ms=8000):
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            cards = page.locator(".SearchPanelitembox")
            exact = page.get_by_text(str(target), exact=True)
            for index in range(min(cards.count(), 20)):
                card = cards.nth(index)
                if not card.is_visible():
                    continue
                try:
                    if card.locator("text=" + str(target)).count() == 0 and exact.count() > 0:
                        continue
                except Exception:
                    pass
                button = card.get_by_text(re.compile(r"^(发消息|发私信|聊天)$")).first
                if button.count() > 0 and button.is_visible():
                    return button, ".SearchPanelitembox"
        except Exception:
            pass

        for selector in CHAT_BUTTON_SELECTORS:
            try:
                buttons = page.locator(selector)
                visible = []
                for index in range(min(buttons.count(), 20)):
                    button = buttons.nth(index)
                    if not button.is_visible():
                        continue
                    text = norm(button.inner_text(timeout=1000))
                    if "聊天" in text or "发消息" in text or "发私信" in text or "chat_btn" in selector:
                        visible.append(button)
                if len(visible) == 1:
                    return visible[0], selector
            except Exception:
                continue
        time.sleep(0.25)
    return None, ""


def _conversation_title(item):
    for selector in CONVERSATION_TITLE_SELECTORS:
        try:
            title = item.locator(selector).first
            if title.count() > 0:
                text = norm(title.inner_text(timeout=1000))
                if text:
                    return text
        except Exception:
            continue
    try:
        return norm(item.inner_text(timeout=1000).splitlines()[0])
    except Exception:
        return ""


def _visible_conversation_items(page):
    for selector in CONVERSATION_ITEM_SELECTORS:
        try:
            items = page.locator(selector)
            if items.count() > 0:
                return items, selector
        except Exception:
            continue
    return None, ""


def _conversation_list(page):
    for selector in CONVERSATION_LIST_SELECTORS:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                return locator, selector
        except Exception:
            continue
    return None, ""


def find_conversation_by_identifier(page, username, target, click=True):
    """Resolve a short_id/unique_id/sec_uid via IM responses while scrolling chats."""
    target = norm(target)
    ensure_chat_ready(page, username)
    scrollable, list_selector = _conversation_list(page)
    if scrollable is None:
        diagnose(page, username, f"conversation-list-not-found:{target}")
        return False

    seen_titles = set()
    stagnant_rounds = 0
    last_scroll_top = None

    for _ in range(50):
        display_name = norm(userIDDict.get(target))
        items, item_selector = _visible_conversation_items(page)
        if items is not None:
            count = min(items.count(), 80)
            for index in range(count):
                item = items.nth(index)
                try:
                    if not item.is_visible():
                        continue
                except Exception:
                    continue
                title = _conversation_title(item)
                if title:
                    seen_titles.add(title)
                if title and (title == target or (display_name and title == display_name)):
                    logger.info(
                        f"账号 {username} 已通过 {matchMode} 映射定位目标 {target}: {title} "
                        f"({item_selector})"
                    )
                    if click:
                        item.click()
                        page.wait_for_timeout(1200)
                    return True

        page.wait_for_timeout(500)
        display_name = norm(userIDDict.get(target))
        if display_name and display_name in seen_titles:
            items, _ = _visible_conversation_items(page)
            if items is not None:
                for index in range(min(items.count(), 80)):
                    item = items.nth(index)
                    if _conversation_title(item) == display_name:
                        logger.info(
                            f"账号 {username} 已通过好友信息接口映射定位目标 {target}: {display_name}"
                        )
                        if click:
                            item.click()
                            page.wait_for_timeout(1200)
                        return True

        try:
            before = scrollable.evaluate("el => el.scrollTop")
            scrollable.evaluate("el => { el.scrollTop += Math.max(600, el.clientHeight * 0.8); }")
            page.wait_for_timeout(max(700, min(1800, config["friendListTimeout"])))
            after = scrollable.evaluate("el => el.scrollTop")
        except Exception as exc:
            logger.debug(f"滚动会话列表失败: {exc}")
            break

        if after == before or after == last_scroll_top:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
        last_scroll_top = after

        if stagnant_rounds >= 4:
            break

    logger.warning(
        f"账号 {username} 未能通过 {matchMode} 在会话列表中定位目标 {target}; "
        f"已收集 {len(userIDDict)} 个 ID 映射、扫描 {len(seen_titles)} 个会话标题、列表 {list_selector}"
    )
    return False


def search_target(page, username, target, click=True):
    target = str(target).strip()

    if matchMode == "short_id":
        if find_conversation_by_identifier(page, username, target, click=click):
            return True
        diagnose(page, username, f"short-id-not-found:{target}")
        raise RuntimeError(
            f"未能在已加载的抖音会话中匹配 short_id {target}。"
            "已尝试好友信息接口映射和滚动会话列表。"
        )

    search_input = get_search_input(page, username)
    try:
        search_input.click()
        search_input.fill("")
        search_input.fill(target)
    except Exception as exc:
        diagnose(page, username, f"search-input-failed:{target}")
        raise RuntimeError(f"无法在抖音 Web Chat 搜索目标 {target}: {exc}") from exc

    time.sleep(max(1.2, min(3.0, config["friendListTimeout"] / 1000)))
    button, selector = find_chat_button(page, target)
    if button is None:
        diagnose(page, username, f"search-result-not-found:{target}")
        raise RuntimeError(f"搜索目标 {target} 后未找到唯一可确认的聊天/发消息按钮")

    logger.info(f"账号 {username} 搜索到目标 {target}: {selector}")
    if click:
        button.click()
        time.sleep(1.2)
    return True


def get_chat_editor(page, username, target):
    editor, selector = wait_for_any_visible(
        page,
        CHAT_EDITOR_SELECTORS,
        min(config["browserTimeout"], 30000),
    )
    if editor is None:
        diagnose(page, username, f"editor-not-ready:{target}")
        raise RuntimeError(f"已选中目标 {target}，但聊天输入框未加载")
    logger.debug(f"账号 {username} 使用输入框选择器: {selector}")
    return editor


def send_message(page, username, target):
    editor = get_chat_editor(page, username, target)
    message = str(build_message() or "")
    if not message.strip():
        raise RuntimeError("消息模板生成结果为空，已取消发送")

    editor.click()
    lines = message.split("\\n")
    for index, line in enumerate(lines):
        page.keyboard.insert_text(line)
        if index < len(lines) - 1:
            page.keyboard.press("Shift+Enter")
    page.keyboard.press("Enter")
    logger.info(f"账号 {username} 已向目标 {target} 提交消息")
    time.sleep(2)


def do_user_task(browser, username, cookies, targets):
    context, page = open_chat_page(browser, username, cookies)
    try:
        ensure_chat_ready(page, username)
        sent = []
        for target in targets:
            search_target(page, username, target, click=True)
            send_message(page, username, str(target))
            sent.append(str(target))

        expected = {str(target) for target in targets}
        if set(sent) != expected:
            raise RuntimeError("部分目标未完成发送: " + ", ".join(sorted(expected - set(sent))))
        logger.info(f"账号 {username} 已完成 {len(sent)} 个目标好友消息任务")
    finally:
        context.close()


def smoke_user(browser, username, cookies, targets):
    context, page = open_chat_page(browser, username, cookies)
    try:
        ensure_chat_ready(page, username)
        if targets:
            search_target(page, username, targets[0], click=False)
        logger.info(f"账号 {username} smoke test 通过：登录态、Web Chat 和目标匹配均可用")
    finally:
        context.close()


def _run_with_browser(worker, label):
    if not userData:
        raise RuntimeError("没有可执行账号，请检查 TASKS 与 COOKIES_<UNIQUE_ID>")
    playwright, browser = get_browser()
    if not playwright or not browser:
        raise RuntimeError("Playwright 浏览器启动失败")
    try:
        logger.info(label)
        for user in userData:
            username = user.get("username", "未知用户")
            logger.info(f"开始处理账号 {username}")
            worker(browser, username, user["cookies"], user["targets"])
            logger.info(f"账号 {username} 完成")
    finally:
        browser.close()
        playwright.stop()


def runTasks():
    _run_with_browser(do_user_task, "开始执行任务")


def smokeTasks():
    _run_with_browser(smoke_user, "开始执行 SparkFlow Web Chat smoke test（不会发送消息）")
