import ast
import inspect
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

import LINELib
from LINELib import ChatService, LineBot, SSEEvent, SSEParser
from LINELib.AuthService import AuthService
from LINELib.LINELib import LINELib as LibraryClient


ROOT = Path(__file__).resolve().parents[1]


def markdown_files():
    return [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]


def github_anchor(heading):
    heading = re.sub(r"[`*_~]", "", heading.strip().lower())
    heading = re.sub(r"[^\w\- ]", "", heading)
    return re.sub(r"-+", "-", heading.replace(" ", "-")).strip("-")


def public_methods(cls):
    return {
        name
        for name, member in cls.__dict__.items()
        if not name.startswith("_") and (callable(member) or isinstance(member, property))
    }


class DocumentationTests(unittest.TestCase):
    def test_python_examples_parse(self):
        for path in sorted((ROOT / "example").glob("*.py")):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_markdown_python_blocks_parse(self):
        block_count = 0
        for path in markdown_files():
            text = path.read_text(encoding="utf-8")
            blocks = re.findall(r"```python\s*\n(.*?)```", text, flags=re.DOTALL)
            block_count += len(blocks)
            for index, block in enumerate(blocks):
                with self.subTest(path=path.relative_to(ROOT), block=index):
                    ast.parse(block, filename=f"{path.name} block {index}")
        self.assertGreater(block_count, 0)

    def test_markdown_relative_links_and_anchors_exist(self):
        for path in markdown_files():
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if re.match(r"^[a-z]+://", target):
                    continue
                file_target, _, fragment = target.partition("#")
                target_path = (path.parent / file_target).resolve() if file_target else path
                with self.subTest(path=path.relative_to(ROOT), target=target):
                    self.assertTrue(target_path.exists(), f"missing target: {target_path}")
                    if fragment and target_path.suffix.lower() == ".md":
                        target_text = target_path.read_text(encoding="utf-8")
                        anchors = {
                            github_anchor(match.group(1))
                            for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", target_text, flags=re.MULTILINE)
                        }
                        self.assertIn(unquote(fragment).lower(), anchors)

    def test_markdown_linebot_calls_exist(self):
        calls = set()
        for path in markdown_files():
            text = path.read_text(encoding="utf-8")
            blocks = re.findall(r"```python\s*\n(.*?)```", text, flags=re.DOTALL)
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

    def test_interactive_browser_defaults_to_chrome(self):
        self.assertEqual(
            "chrome",
            inspect.signature(LineBot).parameters["browser_channel"].default,
        )
        self.assertEqual(
            "chrome",
            inspect.signature(LibraryClient).parameters["browser_channel"].default,
        )
        self.assertEqual(
            "chrome",
            inspect.signature(AuthService.login_with_email_and_2fa)
            .parameters["browser_channel"]
            .default,
        )

    def test_readme_user_agents_match_auth_service(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        authentication = (ROOT / "docs" / "authentication.md").read_text(encoding="utf-8")
        self.assertIn(AuthService.WINDOWS_CHROME_USER_AGENT, readme)
        self.assertIn(AuthService.WINDOWS_EDGE_USER_AGENT, readme)
        self.assertIn(AuthService.WINDOWS_CHROME_USER_AGENT, authentication)
        self.assertIn(AuthService.WINDOWS_EDGE_USER_AGENT, authentication)
        self.assertIn(AuthService.WINDOWS_CHROME_SEC_CH_UA, authentication)
        self.assertIn(AuthService.WINDOWS_EDGE_SEC_CH_UA, authentication)

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

    def test_api_references_cover_all_public_methods(self):
        references = {
            LineBot: ROOT / "docs" / "linebot-api.md",
            LibraryClient: ROOT / "docs" / "low-level-api.md",
            ChatService: ROOT / "docs" / "low-level-api.md",
            AuthService: ROOT / "docs" / "low-level-api.md",
            SSEEvent: ROOT / "docs" / "low-level-api.md",
            SSEParser: ROOT / "docs" / "low-level-api.md",
        }
        for cls, path in references.items():
            text = path.read_text(encoding="utf-8")
            for method in sorted(public_methods(cls)):
                with self.subTest(cls=cls.__name__, method=method):
                    self.assertIn(f"`{method}", text)

    def test_constructor_parameters_are_documented(self):
        references = {
            LineBot: ROOT / "docs" / "linebot-api.md",
            LibraryClient: ROOT / "docs" / "low-level-api.md",
            ChatService: ROOT / "docs" / "low-level-api.md",
            AuthService: ROOT / "docs" / "low-level-api.md",
        }
        for cls, path in references.items():
            text = path.read_text(encoding="utf-8")
            for parameter in inspect.signature(cls).parameters.values():
                with self.subTest(cls=cls.__name__, parameter=parameter.name):
                    self.assertIn(parameter.name, text)

    def test_package_versions_match(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"', pyproject, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), LINELib.__version__)
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"LINELib {LINELib.__version__}", docs_index)

    def test_release_workflow_runs_tests_before_building(self):
        workflow = (ROOT / ".github" / "workflows" / "python-publish.yml").read_text(
            encoding="utf-8"
        )

        test_position = workflow.find("python -m unittest discover -v")
        build_position = workflow.find("python -m build")
        self.assertGreaterEqual(test_position, 0)
        self.assertGreater(build_position, test_position)


if __name__ == "__main__":
    unittest.main()
