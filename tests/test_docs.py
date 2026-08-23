import ast
import re
import unittest
from pathlib import Path

import LINELib
from LINELib import LineBot


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
