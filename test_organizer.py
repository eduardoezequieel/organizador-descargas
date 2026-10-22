import os
from datetime import date
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from organizer import Organizer


class Tests(unittest.TestCase):
    def test_moves_only_selected_type_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, dest = root / 'source', root / 'dest'
            source.mkdir()
            dest.mkdir()
            daily = dest / date.today().isoformat()
            daily.mkdir()
            (daily / 'invoice.json').write_text('old')
            for name in ('invoice.json', 'keep.pdf', 'loading.json'):
                path = source / name
                path.write_text('new')
                os.utime(path, (time.time() - 30,) * 2)
            (source / 'loading.json.part').write_text('partial')
            engine = Organizer(source, {'.json': dest}, lambda _: None)
            stop = threading.Event()
            engine.scan(stop)
            self.assertTrue((source / 'invoice.json').exists())
            engine.scan(stop)
            self.assertFalse((source / 'invoice.json').exists())
            self.assertEqual((daily / 'invoice.json').read_text(), 'old')
            self.assertEqual((daily / 'invoice (1).json').read_text(), 'new')
            self.assertTrue((source / 'keep.pdf').exists())
            self.assertTrue((source / 'loading.json').exists())

    def test_paused_and_recent_files_stay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            path = source / 'new.json'
            path.write_text('{}')
            engine = Organizer(source, {'.json': root / 'dest'}, lambda _: None)
            stop = threading.Event()
            engine.scan(stop)
            engine.scan(stop)
            self.assertTrue(path.exists())
            os.utime(path, (time.time() - 30,) * 2)
            stop.set()
            engine.scan(stop)
            self.assertTrue(path.exists())

    def test_changed_file_is_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            path = source / 'file.json'
            path.write_text('{}')
            engine = Organizer(source, {'.json': root / 'dest'}, lambda _: None)
            with self.assertRaises(OSError):
                engine.move(path, root / 'dest', (999, 0), threading.Event())
            self.assertTrue(path.exists())
            self.assertEqual(list((root / 'dest').iterdir()), [])

    def test_rejects_same_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                Organizer(temp, {'.json': temp})

    def test_groups_both_types_and_changes_day_without_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            rules = {'.json': root / 'json', '.pdf': root / 'pdf'}
            logs = []
            engine = Organizer(source, rules, logs.append)
            stop = threading.Event()
            for day in (date(2026, 10, 21), date(2026, 10, 22)):
                for ext in rules:
                    path = source / ('invoice' + ext)
                    path.write_text(day.isoformat())
                    os.utime(path, (time.time() - 30,) * 2)
                with patch('organizer.date') as clock:
                    clock.today.return_value = day
                    engine.scan(stop)
                    engine.scan(stop)
                for ext, dest in rules.items():
                    target = dest / day.isoformat() / ('invoice' + ext)
                    self.assertEqual(target.read_text(), day.isoformat())
                    self.assertFalse((source / ('invoice' + ext)).exists())
                    self.assertTrue(any(str(target) in message for message in logs))
            for ext, dest in rules.items():
                self.assertEqual((dest / '2026-10-21' / ('invoice' + ext)).read_text(), '2026-10-21')

    def test_unavailable_daily_folder_keeps_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, dest = root / 'source', root / 'dest'
            source.mkdir()
            path = source / 'invoice.json'
            path.write_text('{}')
            os.utime(path, (time.time() - 30,) * 2)
            engine = Organizer(source, {'.json': dest}, lambda _: None)
            (dest / date.today().isoformat()).write_text('obstacle')
            engine.scan(threading.Event())
            engine.scan(threading.Event())
            self.assertEqual(path.read_text(), '{}')


if __name__ == '__main__':
    unittest.main()
