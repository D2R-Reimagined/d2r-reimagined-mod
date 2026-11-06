import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import generate_maps as gen
import endgame
import update_map_boss_quality as quality


SOURCES = ('Andarielq (H)', 'Andarielq (H)', 'Duriel (H)',
           'Mephisto (H)', 'Mephisto (H)', 'Baal (H)')
FIELDS = ('Unique', 'Set', 'Rare', 'Magic')
UNIQUE_SET = (850, 850, 850, 900, 941, 993)


class MapBossQuality(unittest.TestCase):
    def test_saved_bosses_and_regeneration_match_tier_quality(self):
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            with self.subTest(bank=bank):
                path = bank / 'treasureclassex.txt'
                table = gen.Table(path)
                for tier, source in enumerate(SOURCES, 1):
                    boss = table.find(0, f'RMap T{tier} Boss')
                    act = table.find(0, source)
                    for field in FIELDS:
                        expected = (str(UNIQUE_SET[tier - 1]) if field in ('Unique', 'Set')
                                    else act[table.col(field)])
                        self.assertEqual(boss[table.col(field)], expected)
                wrappers = [(r[0], r[table.col('Item1')]) for r in table.rows
                            if r[0].startswith('RMap Entry ')]
                regenerated = endgame.treasure_classes(
                    gen, gen.plan(), path, {'entry_classes': wrappers})
                self.assertEqual(regenerated.to_bytes(), path.read_bytes())

    def test_local_script_updates_both_banks_without_copying_other_cells(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            originals = {}
            for bank, rare in (('', '901'), ('base', '902')):
                path = root / 'data/global/excel' / bank / 'treasureclassex.txt'
                path.parent.mkdir(parents=True, exist_ok=True)
                table = gen.Table(gen.EXCEL / bank / 'treasureclassex.txt')
                table.find(0, 'Duriel (H)')[table.col('Rare')] = rare
                for tier in range(1, 7):
                    boss = table.find(0, f'RMap T{tier} Boss')
                    for field in FIELDS:
                        boss[table.col(field)] = ''
                path.write_bytes(table.to_bytes())
                originals[path] = table
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(quality.main(['--root', str(root), '--check']), 1)
                self.assertEqual(quality.main(['--root', str(root)]), 0)
                first = {p: p.read_bytes() for p in originals}
                self.assertEqual(quality.main(['--root', str(root)]), 0)
                self.assertEqual(quality.main(['--root', str(root), '--check']), 0)
            for path, before in originals.items():
                after = gen.Table(path)
                self.assertEqual(first[path], path.read_bytes())
                self.assertEqual(before.header, after.header)
                self.assertEqual(len(before.rows), len(after.rows))
                for old, new in zip(before.rows, after.rows):
                    expected = list(old)
                    if old[0] in {f'RMap T{t} Boss' for t in range(1, 7)}:
                        tier = int(old[0][6])
                        source = SOURCES[tier - 1]
                        act = before.find(0, source)
                        for field in FIELDS:
                            expected[before.col(field)] = (
                                str(UNIQUE_SET[tier - 1]) if field in ('Unique', 'Set')
                                else act[before.col(field)])
                    self.assertEqual(new, expected, old[0])
                # The full generator must also use this bank's own source values.
                wrappers = [(r[0], r[after.col('Item1')]) for r in after.rows
                            if r[0].startswith('RMap Entry ')]
                regenerated = endgame.treasure_classes(
                    gen, gen.plan(), path, {'entry_classes': wrappers})
                self.assertEqual(regenerated.to_bytes(), path.read_bytes())

    def test_invalid_second_bank_leaves_first_bank_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'data/global/excel/treasureclassex.txt'
            path.parent.mkdir(parents=True)
            table = gen.Table(gen.EXCEL / 'treasureclassex.txt')
            table.find(0, 'RMap T1 Boss')[table.col('Unique')] = ''
            before = table.to_bytes()
            path.write_bytes(before)
            second = path.parent / 'base/treasureclassex.txt'
            second.parent.mkdir()
            second.write_bytes(before.replace(b'Baal (H)\t', b'Missing Baal (H)\t', 1))
            with self.assertRaises(ValueError):
                quality.main(['--root', str(root)])
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
