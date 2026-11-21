"""The soft-mod (standard) build: maps recipes removed, maps strings empty, nothing else touched."""
import hashlib
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
        cls.string_keys = gen.generated_string_keys(cls.plans)
        cls.rules = soft_mod.rules(STUDIO)
        cls.profile_dir = gen.REPO / soft_mod.PROFILE
        cls.profile = json.loads((cls.profile_dir / 'profile.json').read_text(encoding='utf-8'))

    def test_profile_is_up_to_date(self):
        from studio_tables import dumps
        self.assertEqual(soft_mod.write(STUDIO, gen.REPO, dumps, self.string_keys, check=True), [])

    def test_profile_lists_only_the_cube_rule_set(self):
        self.assertEqual([x for x in self.profile['tableOverrides'] if x.startswith(soft_mod.FOLDER + '/')],
                         [f'{soft_mod.FOLDER}/cubemain.json'])
        rule_set = json.loads((self.profile_dir / soft_mod.FOLDER / 'cubemain.json').read_text(encoding='utf-8'))
        self.assertEqual(rule_set['generator'], soft_mod.GENERATOR)
        self.assertEqual(rule_set['rules'], self.rules)

    def test_exactly_the_maps_recipes_are_removed_and_they_end_the_table(self):
        header, _ = STUDIO.read_table(soft_mod.CUBE)
        desc = header.index('description')
        records = STUDIO.read_records(soft_mod.CUBE)
        removed = {r['record'] for r in self.rules}
        self.assertTrue(all(r['remove'] is True and r['reason'] and 'changes' not in r for r in self.rules))
        maps = {sid for sid, row in records if row[desc].split()[:1] == [cfg.CUBE_TAG]}
        self.assertEqual(removed, maps)
        self.assertEqual(len(removed), 680)
        # Mod Studio only removes a table's last rows, so nothing the build keeps moves.
        self.assertEqual({sid for sid, _ in records[-len(removed):]}, removed)
        high = [sid for sid, row in records if any(int(m) > 255 for c in row for m in re.findall(r'lvl=(\d+)', c))]
        self.assertEqual(len(high), 30)
        self.assertTrue(set(high) <= removed, 'portal levels above 255 need the loader')

    def test_treasure_classes_are_not_touched(self):
        self.assertFalse([x for x in self.profile['tableOverrides'] if 'treasureclass' in x])

    def test_every_generated_string_ships_empty(self):
        self.assertEqual(sorted(self.string_keys), ['item-names.json', 'levels.json', 'monsters.json'])
        self.assertGreater(sum(map(len, self.string_keys.values())), 400)
        for name, keys in self.string_keys.items():
            doc = json.loads(STUDIO.catalog_file(f'local/lng/strings/{name}').read_text(encoding='utf-8'))
            locales = doc['schema']['locales']
            seen = set()
            for record in doc['records']:
                if record['Key'] not in keys:
                    continue
                seen.add(record['Key'])
                self.assertEqual(record.get('standardTranslations'), {loc: '' for loc in locales}, record['Key'])
                for loc in locales:
                    full = record['translations'].get(loc) or ''
                    self.assertEqual(record['standardReviewedAgainst'][loc], hashlib.sha256(full.encode('utf-8')).hexdigest())
            self.assertEqual(seen, keys, name)

    def test_generated_strings_are_what_gen_strings_writes(self):
        # Every entry gen_strings writes is one the ownership rule names, so the soft-mod build empties all of them.
        written = gen.gen_strings(self.plans)
        current = gen.string_catalogs()
        for name, entries in written.items():
            hand = {e['Key'] for e in current[name] if e['Key'] not in self.string_keys[name]}
            added = {e['Key'] for e in entries} - hand
            self.assertTrue(added, name)
            self.assertLessEqual(added, self.string_keys[name], f'{name}: gen_strings writes entries the soft-mod build would ship')

    def test_only_generated_strings_ship_empty(self):
        for target in STUDIO.catalog_targets():
            name = target.rsplit('/', 1)[1]
            doc = json.loads(STUDIO.catalog_file(target).read_text(encoding='utf-8'))
            for record in doc['records']:
                compact = record.get('standardTranslations') or {}
                if compact and all(v == '' for v in compact.values()):
                    self.assertIn(record['Key'], self.string_keys.get(name, set()),
                                  f'{name}: {record["Key"]} ships empty but is not a maps string')


if __name__ == '__main__':
    unittest.main()
