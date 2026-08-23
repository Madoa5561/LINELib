import ast
import inspect
import re
import unittest
from pathlib import Path

import LINELib
from LINELib import LineBot
from LINELib.AuthService import AuthService
from LINELib.LINELib import LINELib as LibraryClient


ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_python_examples_parse(self):
        for path in sorted((ROOT / "example").glob("*.py")):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_readme_python_blocks_parse(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```python\s*\n(.*?)```", readme, flags=re.DOTALL)
        self.assertTrue(blocks)
        for index, block in enumerate(blocks):
            with self.subTest(block=index):
                ast.parse(block, filename=f"README.md block {index}")

    def test_readme_linebot_calls_exist(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```python\s*\n(.*?)```", readme, flags=re.DOTALL)
        calls = set()
        for block in blocks:
            tree = ast.parse(block)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "bot"
                ):
                    calls.add(node.func.attr)
        self.assertFalse(calls.difference(dir(LineBot)))

    def test_examples_use_shared_login_helper_and_public_imports(self):
        runnable_examples = [
            path
            for path in sorted((ROOT / "example").glob("*.py"))
            if not path.name.startswith("_")
        ]
        self.assertTrue(runnable_examples)
        for path in runnable_examples:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                if path.name == "example_login_edge.py":
                    self.assertIn('browser_channel="msedge"', source)
                    self.assertIn("interactive_login=True", source)
                    self.assertIn("getpass(", source)
                else:
                    self.assertIn("from _login import", source)
                self.assertNotIn("from LINELib.", source)

    def test_example_api_calls_exist(self):
        clients = {"bot": LineBot, "lib": LibraryClient}
        for path in sorted((ROOT / "example").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in clients
                ):
                    with self.subTest(path=path.name, method=node.func.attr):
                        self.assertTrue(hasattr(clients[node.func.value.id], node.func.attr))

    def test_readme_lists_example_files_and_environment_variables(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        example_sources = []
        for path in sorted((ROOT / "example").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            example_sources.append(source)
            if not path.name.startswith("_"):
                self.assertIn(f"`{path.name}`", readme)

        environment_names = set()
        for source in example_sources:
            environment_names.update(
                re.findall(r'os\.environ(?:\.get)?\(["\']([A-Z0-9_]+)["\']', source)
            )
            environment_names.update(
                re.findall(r'os\.environ\[["\']([A-Z0-9_]+)["\']\]', source)
            )
        for name in sorted(environment_names):
            with self.subTest(environment=name):
                self.assertIn(f"`{name}`", readme)

    def test_interactive_browser_defaults_to_edge(self):
        self.assertEqual(
            "msedge",
            inspect.signature(LineBot).parameters["browser_channel"].default,
        )
        self.assertEqual(
            "msedge",
            inspect.signature(LibraryClient).parameters["browser_channel"].default,
        )
        self.assertEqual(
            "msedge",
            inspect.signature(AuthService.login_with_email_and_2fa)
            .parameters["browser_channel"]
            .default,
        )

    def test_documented_linebot_methods_exist(self):
        methods = {
            "sendMessage",
            "sendFile",
            "listen",
            "stop",
            "event",
            "normalize_message_event",
            "save_message_media",
            "save_image_preview",
            "save_sticker_image",
        }
        self.assertFalse(methods.difference(dir(LineBot)))

    def test_package_versions_match(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"', pyproject, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), LINELib.__version__)


if __name__ == "__main__":
    unittest.main()
