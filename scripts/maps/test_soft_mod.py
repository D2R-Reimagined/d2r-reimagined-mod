"""The soft-mod (standard) profile rules: exterior maps off, nothing else touched."""
import json
import re
import unittest

import generate_maps as gen
import maps_config as cfg
import soft_mod

STUDIO = gen.studio()


@unittest.skipUnless(STUDIO is not None, 'not a Mod Studio project')
class SoftModProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans = gen.plan()
        cls.rules = soft_mod.rules(STUDIO, cls.plans)
        cls.profile_dir = gen.REPO / soft_mod.PROFILE

    _records: dict = {}

    def records(self, target):
        if target not in self._records:
            self._records[target] = dict(STUDIO.read_records(target))
        return self._records[target]

    def test_rules_on_disk_and_listed_in_the_profile(self):
        from studio_tables import dumps
        self.assertEqual(soft_mod.write(STUDIO, gen.REPO, self.plans, dumps, check=True), [])
        listed = json.loads((self.profile_dir / 'profile.json').read_text(encoding='utf-8'))['tableOverrides']
        sets = soft_mod.rule_sets(self.rules)
        self.assertEqual(sorted(x for x in listed if x.startswith(soft_mod.FOLDER + '/')), sorted(sets))
        self.assertEqual(sorted(sets), sorted(f'{soft_mod.FOLDER}/{n}.json' for n in ('cubemain', 'treasureclassex', 'treasureclassex-base')))
        for name, rule_set in sets.items():
            self.assertEqual(rule_set['generator'], soft_mod.GENERATOR)
            self.assertTrue(all(r['table'] == name.split('/')[1][:-5] for r in rule_set['rules']), name)

    def test_one_rule_per_record(self):
        keys = [(r['table'], r['record']) for r in self.rules]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_rule_expects_the_current_cell(self):
        targets = {STUDIO.table_name(t): t for t in ('global/excel/cubemain.txt',) + soft_mod.TREASURE}
        headers = {t: STUDIO.read_table(t)[0] for t in targets.values()}
        for rule in self.rules:
            name = f"{rule['table']}/{rule['record']}"
            target = targets[rule['table']]
            header = headers[target]
            row = self.records(target)[rule['record']]
            for column, change in rule['changes'].items():
                self.assertEqual(row[header.index(column)], change['expect'], name)
                self.assertTrue(rule['reason'])

    def test_exactly_the_exterior_recipes_are_disabled(self):
        header, _ = STUDIO.read_table('global/excel/cubemain.txt')
        desc, enabled = header.index('description'), header.index('enabled')
        disabled = {r['record'] for r in self.rules if r['table'] == 'cubemain'}
        exterior = set(soft_mod.exterior_keys())
        self.assertEqual(len(exterior), 5)
        seen_high = 0
        for source_id, row in STUDIO.read_records('global/excel/cubemain.txt'):
            words = row[desc].split()
            is_ext = len(words) >= 3 and words[0] == cfg.CUBE_TAG and words[2] in exterior
            self.assertEqual(source_id in disabled, is_ext and row[enabled] != '0', row[desc])
            levels = [int(m) for c in row for m in re.findall(r'lvl=(\d+)', c)]
            if any(l > 255 for l in levels):
                seen_high += 1
                self.assertIn(source_id, disabled, f'{row[desc]}: portal level above 255 needs the loader')
        self.assertEqual(seen_high, 30)

    def test_no_treasure_class_drops_an_exterior_map(self):
        partners = soft_mod.interior_partners(self.plans)
        exterior_codes = set(partners)
        self.assertFalse(exterior_codes & set(partners.values()))
        for target in soft_mod.TREASURE:
            header, _ = STUDIO.read_table(target)
            items = [header.index(f'Item{i}') for i in range(1, 11)]
            table = STUDIO.table_name(target)
            swaps = {r['record']: r['changes'] for r in self.rules if r['table'] == table}
            self.assertTrue(swaps, target)
            for source_id, row in STUDIO.read_records(target):
                for c in items:
                    if row[c] in exterior_codes:
                        change = swaps[source_id][header[c]]
                        self.assertEqual(change['value'], partners[row[c]])

    def test_partners_keep_the_tier(self):
        for exterior, interior in soft_mod.interior_partners(self.plans).items():
            self.assertEqual(exterior[-1], interior[-1])


if __name__ == '__main__':
    unittest.main()
