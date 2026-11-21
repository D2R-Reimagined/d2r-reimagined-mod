import json
import unittest

import generate_maps as gen
import normal_shamans


class NormalShamanContract(unittest.TestCase):
    def test_both_banks_and_regeneration(self):
        models = json.loads((gen.REPO / 'data/hd/character/monsters.json').read_text())
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            monsters = gen.Table(bank / 'monstats.txt')
            levels = gen.Table(bank / 'levels.txt')
            before_monsters, before_levels = monsters.to_bytes(), levels.to_bytes()
            runtime = {}
            normal_shamans.generate(gen, monsters, levels, runtime)
            self.assertEqual(before_monsters, monsters.to_bytes())
            self.assertEqual(before_levels, levels.to_bytes())
            for source in normal_shamans.SOURCES:
                name = normal_shamans.REPLACEMENTS[source]
                original = monsters.find(monsters.col('Id'), source)
                clone = monsters.find(monsters.col('Id'), name)
                for col in ('MinGrp', 'MaxGrp'):
                    self.assertEqual(original[monsters.col(col)], '2')
                    self.assertEqual(clone[monsters.col(col)], '1')
                for i, col in enumerate(monsters.header):
                    if col not in ('Id', '*hcIdx', 'NextInClass', 'MinGrp', 'MaxGrp'):
                        self.assertEqual(original[i], clone[i], col)
                self.assertEqual(models[name], models[source])
            references = 0
            for row in levels.rows:
                for i, col in enumerate(levels.header):
                    value = row[i]
                    self.assertFalse(value.startswith('rmap_normal_'))
                    if value in normal_shamans.REPLACEMENTS.values():
                        references += 1
                        self.assertEqual(row[levels.col('Act')], '0')
                        self.assertTrue(col.startswith(('mon', 'umon')), col)
                        self.assertIn(value.removesuffix('_normal'), normal_shamans.SOURCES)
                    if row[levels.col('Act')] == '0' and col.startswith(('mon', 'umon')):
                        self.assertNotIn(value, normal_shamans.SOURCES)
            self.assertGreater(references, 0)


if __name__ == '__main__':
    unittest.main()
