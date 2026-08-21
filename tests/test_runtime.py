import os
import unittest
from unittest.mock import patch

from core.runtime import RunMode, resolve_run_mode


class RuntimeTests(unittest.TestCase):
    def test_default_mode_is_send(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIs(resolve_run_mode(), RunMode.SEND)

    def test_explicit_mode_wins(self):
        with patch.dict(os.environ, {"SPARKFLOW_MODE": "send"}, clear=True):
            self.assertIs(resolve_run_mode("smoke"), RunMode.SMOKE)

    def test_environment_mode(self):
        with patch.dict(os.environ, {"SPARKFLOW_MODE": "smoke"}, clear=True):
            self.assertIs(resolve_run_mode(), RunMode.SMOKE)

    def test_legacy_smoke_flag_still_works(self):
        with patch.dict(os.environ, {"SPARKFLOW_SMOKE_TEST": "1"}, clear=True):
            self.assertIs(resolve_run_mode(), RunMode.SMOKE)


if __name__ == "__main__":
    unittest.main()
