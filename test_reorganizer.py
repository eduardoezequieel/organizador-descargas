from datetime import datetime
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from organizer import Reorganizer


class ReorganizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.rules = {'.json': self.root / 'json', '.pdf': self.root / 'pdf'}
        for folder in self.rules.values():
            folder.mkdir()
        self.stamp = datetime(2024, 5, 7, 12).timestamp()
        self.stop = threading.Event()
        self.logs = []
        self.engine = Reorganizer(self.rules, self.logs.append)

    def file(self, path, content='example'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        os.utime(path, (self.stamp, self.stamp))
        return path

    def test_root_nested_collisions_metadata_and_repeat(self):
        json = self.rules['.json']
        pdf = self.rules['.pdf']
        original = self.file(json / '2024-05-07' / 'invoice.json', 'existing')
        incoming = self.file(json / 'old' / 'nested' / 'invoice.json', 'incoming')
        document = self.file(pdf / 'document.PDF')
        untouched = self.file(json / 'notes.txt')
        result = self.engine.run_once(self.stop)
        self.assertEqual(result, dict(moved=2, unchanged=1, skipped=0, errors=0))
        self.assertFalse(incoming.exists())
        self.assertFalse(document.exists())
        self.assertEqual(original.read_text(), 'existing')
        moved = json / '2024-05-07' / 'invoice (1).json'
        self.assertEqual(moved.read_text(), 'incoming')
        self.assertEqual(moved.stat().st_mtime, self.stamp)
        self.assertTrue((pdf / '2024-05-07' / 'document.PDF').exists())
        self.assertTrue(untouched.exists())
        self.assertEqual(self.engine.run_once(self.stop), dict(moved=0, unchanged=3, skipped=0, errors=0))

    def test_pending_files_and_stop(self):
        pending = self.file(self.rules['.json'] / 'pending.json')
        pending.with_name(pending.name + '.part').touch()
        recent = self.rules['.pdf'] / 'recent.pdf'
        recent.write_text('new')
        self.assertEqual(self.engine.run_once(self.stop)['skipped'], 2)
        self.assertTrue(pending.exists())
        self.assertTrue(recent.exists())
        ready = self.file(self.rules['.json'] / 'ready.json')
        self.stop.set()
        self.assertEqual(self.engine.run_once(self.stop)['moved'], 0)
        self.assertTrue(ready.exists())

    def test_failed_copy_retains_source_and_removes_partial(self):
        source = self.file(self.rules['.json'] / 'invoice.json')
        with patch('organizer.shutil.copystat', side_effect=PermissionError('test')):
            self.assertEqual(self.engine.run_once(self.stop)['errors'], 1)
        self.assertEqual(source.read_text(), 'example')
        self.assertEqual(list((self.rules['.json'] / '2024-05-07').iterdir()), [])

    def test_rejects_nested_destinations(self):
        nested = self.rules['.json'] / 'nested'
        nested.mkdir()
        with self.assertRaises(ValueError):
            Reorganizer({'.json': self.rules['.json'], '.pdf': nested})

    def test_shared_destination_supports_both_types(self):
        folder = self.rules['.json']
        self.file(folder / 'one.json')
        self.file(folder / 'two.pdf')
        engine = Reorganizer({'.json': folder, '.pdf': folder}, self.logs.append)
        self.assertEqual(engine.run_once(self.stop)['moved'], 2)


if __name__ == '__main__':
    unittest.main()
