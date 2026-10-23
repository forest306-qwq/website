import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sync_daily_song import save_winner
from update_content import collect


class DailySongTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory(prefix='.daily-song-test-', dir=source)
        self.site = Path(self.temp.name)
        for relative in ['index.html', 'diary.html', 'columns.html', 'assets/song-catalog.json']:
            target = self.site / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target)
        shutil.copytree(source / 'columns', self.site / 'columns')
        self.catalog = json.loads((self.site / 'assets/song-catalog.json').read_text(encoding='utf-8-sig'))
        self.first = self.catalog['33933850']
        self.second = self.catalog['1645112']

    def tearDown(self):
        self.assertTrue(self.site.resolve().is_relative_to(Path(__file__).resolve().parents[1]))
        self.temp.cleanup()

    def add(self, song, date='2026-10-23'):
        return save_winner(self.site, {'status': 'ok', 'date': date, 'song': song})

    def files(self):
        return {p: p.read_bytes() for p in self.site.rglob('*') if p.is_file()}

    def read(self, name):
        return json.loads((self.site / 'data' / name).read_text(encoding='utf-8'))

    def test_one_card_per_day_and_synced_indexes(self):
        before = len([e for e in collect(self.site) if e['category'] == 'song'])
        self.add(self.second)
        original = self.files()
        self.add(self.first)
        self.assertEqual(original, self.files())
        selected = [e for e in collect(self.site) if e['category'] == 'song']
        self.assertEqual(len(selected), before + 1)
        self.assertEqual(next(e for e in selected if e['date'] == '2026-10-23')['song_id'], '1645112')
        html = (self.site / 'columns/song.html').read_text(encoding='utf-8')
        card = html.split('id="song-auto-20261023"', 1)[1].split('</article>', 1)[0]
        self.assertNotIn('song-note', card)
        for target in ['/song?id=1645112', '/artist?id=38053', '/album?id=167078', '<img']:
            self.assertIn(target, card)
        self.assertIn('/columns/song.html#song-auto-20261023', (self.site / 'index.html').read_text(encoding='utf-8'))
        self.assertIn(f'{before + 1} 首', (self.site / 'columns.html').read_text(encoding='utf-8'))

    def test_consecutive_duplicates_skip_without_alternating(self):
        self.add(self.first, '2026-10-23')
        original = (self.site / 'columns/song.html').read_bytes()
        self.add(self.first, '2026-10-24')
        self.add(self.first, '2026-10-25')
        self.assertEqual(original, (self.site / 'columns/song.html').read_bytes())
        self.add(self.second, '2026-10-26')
        self.assertEqual(self.read('daily-songs.json'), {'2026-10-23': '33933850', '2026-10-26': '1645112'})
        self.assertEqual(len(self.read('daily-song-state.json')), 4)
        self.add(self.first, '2026-10-27')  # 前一天不同，允许再次选中。
        self.assertEqual(self.read('daily-songs.json')['2026-10-27'], '33933850')

    def test_manual_song_and_note_preserved_and_yesterday_checked(self):
        original = (self.site / 'columns/song.html').read_bytes()
        self.add(self.second, '2026-10-16')
        self.add(self.first, '2026-10-17')
        self.add(self.first, '2026-10-18')
        self.assertEqual(original, (self.site / 'columns/song.html').read_bytes())
        self.assertFalse((self.site / 'data/daily-songs.json').exists())
        self.assertIn('送给自己的音乐盒', original.decode('utf-8'))

    def test_empty_or_bad_metadata_preserve_content(self):
        original = self.files()
        save_winner(self.site, {'status': 'empty', 'date': '2026-10-23'})
        self.assertEqual(original, self.files())
        with self.assertRaises(ValueError):
            self.add({'id': 1, 'name': 'Missing metadata'})
        self.assertEqual(original, self.files())

    def test_generator_failure_rolls_back_data_and_pages(self):
        original = self.files()
        def broken_sync(site):
            (site / 'index.html').write_text('partial update', encoding='utf-8')
            raise ValueError('simulated failure')
        with patch('sync_daily_song.sync', side_effect=broken_sync):
            with self.assertRaises(ValueError):
                self.add(self.first)
        self.assertEqual(original, self.files())


if __name__ == '__main__':
    unittest.main()
