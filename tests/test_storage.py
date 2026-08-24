import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from LINELib import storage


class StorageTests(unittest.TestCase):
    def test_lock_acquisition_error_is_not_masked_by_unlock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "state.json"
            if os.name == "nt":
                patch_target = "msvcrt.locking"
            else:
                patch_target = "fcntl.flock"

            with patch(
                patch_target,
                side_effect=[OSError("acquire failed"), OSError("unlock failed")],
            ) as lock:
                with self.assertRaisesRegex(OSError, "acquire failed"):
                    with storage._process_lock(str(target)):
                        pass

            lock.assert_called_once()

    def test_body_error_is_not_masked_by_unlock_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "state.json"
            if os.name == "nt":
                patch_target = "msvcrt.locking"
            else:
                patch_target = "fcntl.flock"

            with patch(
                patch_target,
                side_effect=[None, OSError("unlock failed")],
            ) as lock:
                with self.assertRaisesRegex(ValueError, "body failed"):
                    with storage._process_lock(str(target)):
                        raise ValueError("body failed")

            self.assertEqual(2, lock.call_count)

    def test_unlock_error_is_reported_after_successful_body(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "state.json"
            if os.name == "nt":
                patch_target = "msvcrt.locking"
            else:
                patch_target = "fcntl.flock"

            with patch(
                patch_target,
                side_effect=[None, OSError("unlock failed")],
            ):
                with self.assertRaisesRegex(OSError, "unlock failed"):
                    with storage._process_lock(str(target)):
                        pass


if __name__ == "__main__":
    unittest.main()
