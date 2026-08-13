import os
import shutil
import subprocess
import sys
import traceback

from playwright.sync_api import sync_playwright

from utils.config import DEBUG, Environment, get_environment

PLAYWRIGHT_BROWSERS_PATH = "../chrome"


def install_browser():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("浏览器安装完成，请重新运行程序。")
    except subprocess.CalledProcessError as exc:
        print(f"浏览器安装失败：{exc}")


def _system_chrome_path():
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def get_browser():
    headless = True
    env = get_environment()

    if env == Environment.LOCAL:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.abspath(
            os.path.join(os.path.dirname(__file__), PLAYWRIGHT_BROWSERS_PATH)
        )
        if DEBUG:
            headless = False
    elif env == Environment.PACKED:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.abspath(
            os.path.join(os.path.dirname(sys.executable), PLAYWRIGHT_BROWSERS_PATH)
        )

    playwright = None
    try:
        playwright = sync_playwright().start()
        launch_kwargs = {
            "headless": headless,
            "args": ["--disable-dev-shm-usage"],
        }

        # GitHub hosted runners already ship a full Chrome browser. Prefer it over
        # chrome-headless-shell because Douyin Web Chat is a full browser app.
        if env == Environment.GITHUBACTION:
            chrome_path = _system_chrome_path()
            if chrome_path:
                launch_kwargs["executable_path"] = chrome_path
                print(f"Using system Chrome: {chrome_path}")

        browser = playwright.chromium.launch(**launch_kwargs)
        return playwright, browser
    except Exception as exc:
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass
        if "Executable doesn't exist" in str(exc) and env != Environment.GITHUBACTION:
            print("浏览器可执行文件不存在！")
            install_browser()
            sys.exit(1)
        traceback.print_exc()
        return None, None
