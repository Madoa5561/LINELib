import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from LINELib import util


class UtilTests(unittest.TestCase):
    def test_relinking_removes_stale_reverse_mappings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            map_path = Path(temp_dir) / "id_map.json"

            with patch.object(util, "_IDMAP_PATH", str(map_path)):
                util.link_group_and_chat("group-a", "chat-1")
                util.link_group_and_chat("group-a", "chat-2")

                self.assertIsNone(util.get_groupid_from_chatid("chat-1"))
                self.assertEqual("chat-2", util.get_chatid_from_groupid("group-a"))
                self.assertEqual("group-a", util.get_groupid_from_chatid("chat-2"))

                util.link_group_and_chat("group-b", "chat-2")

                self.assertIsNone(util.get_chatid_from_groupid("group-a"))
                self.assertEqual("chat-2", util.get_chatid_from_groupid("group-b"))
                self.assertEqual("group-b", util.get_groupid_from_chatid("chat-2"))

    def test_concurrent_id_map_updates_are_not_lost(self):
        worker_count = 12
        load_barrier = threading.Barrier(worker_count)
        errors = []

        with tempfile.TemporaryDirectory() as temp_dir:
            map_path = Path(temp_dir) / "id_map.json"
            original_load = util._load_idmap

            def synchronized_load():
                data = original_load()
                load_barrier.wait(timeout=2)
                return data

            def link(index):
                try:
                    util.link_group_and_chat(f"group-{index}", f"chat-{index}")
                except Exception as error:
                    errors.append(error)

            with (
                patch.object(util, "_IDMAP_PATH", str(map_path)),
                patch.object(util, "_load_idmap", side_effect=synchronized_load),
            ):
                threads = [threading.Thread(target=link, args=(index,)) for index in range(worker_count)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

                saved = original_load()

        self.assertEqual([], errors)
        self.assertEqual(worker_count, len(saved["group_to_chat"]))
        self.assertEqual(worker_count, len(saved["chat_to_group"]))


if __name__ == "__main__":
    unittest.main()
