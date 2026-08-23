import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lineoa_example_login", ROOT / "example" / "_login.py")
LOGIN_HELPER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(LOGIN_HELPER)


class ExampleLoginTests(unittest.TestCase):
    def test_cookie_only_bot_does_not_enable_interactive_login(self):
        with (
            patch.dict(os.environ, {"LINEOA_COOKIE_PATH": "saved.json"}, clear=True),
            patch.object(LOGIN_HELPER, "LineBot") as line_bot,
        ):
            LOGIN_HELPER.create_bot(ping_secs=30)

        _, kwargs = line_bot.call_args
        self.assertEqual("saved.json", kwargs["cookie_path"])
        self.assertEqual(30, kwargs["ping_secs"])
        self.assertNotIn("email", kwargs)
        self.assertNotIn("interactive_login", kwargs)

    def test_credentials_enable_edge_interactive_login(self):
        environment = {
            "LINEOA_EMAIL": "owner@example.com",
            "LINEOA_PASSWORD": "test-password",
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(LOGIN_HELPER, "LineBot") as line_bot,
        ):
            LOGIN_HELPER.create_bot()

        _, kwargs = line_bot.call_args
        self.assertEqual("owner@example.com", kwargs["email"])
        self.assertEqual("test-password", kwargs["password"])
        self.assertTrue(kwargs["interactive_login"])
        self.assertEqual("msedge", kwargs["browser_channel"])
        self.assertTrue(callable(kwargs["get_2fa_code_callback"]))

    def test_partial_credentials_are_rejected(self):
        with patch.dict(os.environ, {"LINEOA_EMAIL": "owner@example.com"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must be set together"):
                LOGIN_HELPER.create_library()


if __name__ == "__main__":
    unittest.main()
