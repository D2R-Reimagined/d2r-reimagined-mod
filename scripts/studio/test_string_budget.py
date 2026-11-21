"""string_budget: per-locale string text of a build, over the plain game's catalogs."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import string_budget as sb


def entry(i, key, en, ru):
    return {'id': i, 'Key': key, 'enUS': en, 'ruRU': ru}


class StringBudget(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='string-budget-'))
        self.game = self.root / 'game'; self.game.mkdir()
        # The plain game: two catalogs.
        (self.game / 'levels.json').write_text(json.dumps([entry(1, 'A', 'ab', 'аб')]), encoding='utf-8')
        (self.game / 'ui.json').write_text(json.dumps([entry(2, 'B', 'xyz', None)]), encoding='utf-8-sig')
        # The mod: source/strings replaces levels.json, with one entry that ships empty in standard mode.
        strings = self.root / 'repo' / 'source' / 'strings'; strings.mkdir(parents=True)
        doc = {'schema': {'category': 'levels', 'target': 'local/lng/strings/levels.json', 'locales': ['enUS', 'ruRU']},
               'records': [
                   {'id': 1, 'Key': 'A', 'translations': {'enUS': 'ab', 'ruRU': 'аб'}},
                   {'id': 3, 'Key': 'RMap', 'translations': {'enUS': 'Map', 'ruRU': 'Карта'},
                    'standardTranslations': {'enUS': '', 'ruRU': ''}, 'standardReviewedAgainst': {}},
               ]}
        (strings / 'levels.json').write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_budget(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = sb.main(['--repo', str(self.root / 'repo'), '--game-strings', str(self.game), *args])
        return code, out.getvalue()

    def test_totals_count_utf8_bytes_and_characters(self):
        t = sb.totals({'x': [entry(1, 'K', 'ab', 'аб'), entry(2, 'L', None, 'в')]})
        self.assertEqual(t['enUS'], {'bytes': 2, 'chars': 2})
        self.assertEqual(t['ruRU'], {'bytes': 6, 'chars': 3})

    def test_a_mod_catalog_replaces_the_game_file_of_that_name(self):
        game = sb.game_catalogs(self.game)
        mod = sb.source_catalogs(self.root / 'repo', 'full')
        self.assertEqual(sb.totals(sb.loaded(game, mod))['enUS']['bytes'], len('ab' 'Map' 'xyz'))

    def test_standard_mode_uses_the_compact_translations(self):
        game = sb.game_catalogs(self.game)
        standard = sb.totals(sb.loaded(game, sb.source_catalogs(self.root / 'repo', 'standard')))
        full = sb.totals(sb.loaded(game, sb.source_catalogs(self.root / 'repo', 'full')))
        self.assertEqual(full['ruRU']['bytes'] - standard['ruRU']['bytes'], len('Карта'.encode('utf-8')))

    def test_limit(self):
        ru = len('аб'.encode('utf-8'))   # standard build: only the plain game's text in Russian
        self.assertEqual(self.run_budget('--max-bytes', str(ru))[0], 0)
        code, out = self.run_budget('--max-bytes', str(ru - 1))
        self.assertEqual(code, 1); self.assertIn('over the limit', out)
        self.assertEqual(self.run_budget('--mode', 'full', '--max-bytes', str(ru))[0], 1)

    def test_a_built_folder_can_be_measured(self):
        built = self.root / 'built'; built.mkdir()
        (built / 'levels.json').write_text(json.dumps([entry(1, 'A', '', 'абвг')], ensure_ascii=False), encoding='utf-8')
        code, out = self.run_budget('--output', str(built), '--max-bytes', '8')
        self.assertEqual(code, 0, out)
        self.assertEqual(self.run_budget('--output', str(built), '--max-bytes', '7')[0], 1)

    def test_missing_game_strings_is_an_input_error(self):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sb.main(['--repo', str(self.root / 'repo'), '--game-strings', str(self.root / 'nope')]), 2)


if __name__ == '__main__':
    unittest.main()
