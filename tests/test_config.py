import json
import os
import unittest
from unittest.mock import patch

from utils.config import (
    ConfigError,
    get_config,
    get_userData,
    sanitize_cookies,
    validate_runtime_environment,
)


COOKIE = {
    "name": "sessionid",
    "value": "demo",
    "domain": ".douyin.com",
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "no_restriction",
}


class ConfigTests(unittest.TestCase):
    def base_env(self):
        return {
            "TASKS": json.dumps(
                [
                    {
                        "username": "primary",
                        "unique_id": "123456",
                        "targets": ["friend-a", "friend-b"],
                    }
                ]
            ),
            "COOKIES_123456": json.dumps([COOKIE]),
        }

    def test_defaults_and_account_loading(self):
        with patch.dict(os.environ, self.base_env(), clear=True):
            config = get_config()
            users = get_userData()
            summary = validate_runtime_environment()

        self.assertEqual(config["matchMode"], "nickname")
        self.assertEqual(config["browserTimeout"], 120000)
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["targets"], ["friend-a", "friend-b"])
        self.assertEqual(summary["targets"], 2)

    def test_cookie_editor_schema_is_normalized(self):
        cookies = sanitize_cookies([COOKIE])
        self.assertEqual(cookies[0]["sameSite"], "None")
        self.assertEqual(cookies[0]["domain"], ".douyin.com")
        self.assertTrue(cookies[0]["httpOnly"])

    def test_url_cookie_is_supported(self):
        cookie = {"name": "sid", "value": "x", "url": "https://www.douyin.com/chat"}
        normalized = sanitize_cookies([cookie])
        self.assertEqual(normalized[0]["url"], cookie["url"])
        self.assertNotIn("domain", normalized[0])

    def test_missing_cookie_fails_early(self):
        env = self.base_env()
        env.pop("COOKIES_123456")
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigError):
                validate_runtime_environment()

    def test_invalid_match_mode_fails_early(self):
        env = self.base_env() | {"MATCH_MODE": "unknown"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigError):
                get_config()

    def test_duplicate_unique_id_fails(self):
        env = self.base_env()
        tasks = json.loads(env["TASKS"])
        tasks.append({"username": "other", "unique_id": "123456", "targets": ["friend"]})
        env["TASKS"] = json.dumps(tasks)
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigError):
                get_userData()


if __name__ == "__main__":
    unittest.main()
