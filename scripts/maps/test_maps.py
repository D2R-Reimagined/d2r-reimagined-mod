import unittest
import struct
import json
import generate_maps as gen
import maps_config as cfg
import boss_rooms


class MappingContract(unittest.TestCase):
    def test_map_quality_matches_rare_capable_misc_items(self):
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            types = gen.Table(bank / 'itemtypes.txt')
            maps = types.find(types.col('Code'), gen.MAP_ITEM_TYPE)
            self.assertEqual(maps[types.col('Normal')], '0')
            self.assertEqual(maps[types.col('Magic')], '1')
            for reference in ('ring', 'amul'):
                working = types.find(types.col('Code'), reference)
                for field in ('Magic', 'Rare', 'Normal'):
                    self.assertEqual(maps[types.col(field)], working[types.col(field)])
            self.assertEqual(maps[types.col('Rare')], '1')
            self.assertEqual(maps[types.col('VarInvGfx')], '0')
            for slot in range(1, 7):
                self.assertFalse(maps[types.col(f'InvGfx{slot}')])
            currency = types.find(types.col('Code'), gen.MAP_CURRENCY_TYPE)
            self.assertEqual(currency[types.col('Normal')], '1')
            self.assertEqual(currency[types.col('Rare')], '0')
            misc = gen.Table(bank / 'misc.txt')
            for p in self.plans:
                item = misc.find(misc.col('code'), p['item_code'])
                self.assertFalse(item[misc.col('auto prefix')])

    def test_every_map_has_valid_tier_sprites_and_ground_binding(self):
        entries = json.loads((gen.REPO / 'data/hd/items/items.json').read_text())
        lookup = {code: value for entry in entries for code, value in entry.items()}
        for p in self.plans:
            code = p['item_code']
            asset = f'map/map_t{code[-1]}'
            self.assertEqual(lookup[code]['asset'], asset)
            ground = gen.REPO / f'data/hd/items/misc/{asset}.json'
            self.assertTrue(json.loads(ground.read_text())['dependencies']['models'])
            for size, suffix in ((98, ''), (49, '.lowend')):
                sprite = gen.REPO / f'data/hd/global/ui/items/misc/{asset}{suffix}.sprite'
                data = sprite.read_bytes()
                self.assertEqual(struct.unpack('<4sHH8I', data[:40]),
                                 (b'SpA1', 31, size, size, size, 0, 1, 0, 0, size*size*4, 4))
                self.assertEqual(len(data), 40+size*size*4)
                alpha = data[43::4]
                self.assertEqual((min(alpha), max(alpha)), (0, 255))

    def test_native_rare_quality_pool_does_not_grant_carried_stats(self):
        for kind in ('prefix', 'suffix'):
            table = gen.Table(gen.EXCEL / f'magic{kind}.txt')
            row = table.find(table.col('name'), f'{cfg.AFFIX_TAG}_quality_{kind}')
            for field in ('spawnable', 'rare', 'frequency'):
                self.assertEqual(row[table.col(field)], '1')
            self.assertEqual(row[table.col('itype1')], 'mapi')
            for slot in range(1, 4):
                self.assertFalse(row[table.col(f'mod{slot}code')])

    def test_every_generated_monster_has_its_source_hd_model(self):
        models = json.loads((gen.REPO / 'data/hd/character/monsters.json').read_text(encoding='utf-8-sig'))
        for row in self.monsters.rows:
            name = row[self.monsters.col('Id')]
            if name.startswith('rmap_'):
                self.assertIn(name, models)
                self.assertTrue(models[name])
        for p in self.plans:
            sources = cfg.MAP_MONSTERS[p['theme']['key']]
            for i, source in enumerate(sources):
                self.assertEqual(models[f"rmap_{p['item_code']}_{i}"], models[source])
            self.assertEqual(models[f"rmap_{p['item_code']}_boss"], models[sources[0]])
        self.assertEqual(models['rmap_md1_0'], models['vampire5'])

    @classmethod
    def setUpClass(cls):
        cls.plans = gen.plan()
        cls.levels = gen.Table(gen.EXCEL / "levels.txt")
        cls.monsters = gen.Table(gen.EXCEL / "monstats.txt")
        cls.props = gen.Table(gen.EXCEL / "monprop.txt")

    def test_maps_have_independent_combat_population_and_persistent_kills(self):
        for p in self.plans:
            level = self.levels.find(self.levels.col("Id"), str(p["body_id"]))
            self.assertEqual(level[self.levels.col("SaveMonsters")], "1")
            self.assertEqual(int(level[self.levels.col("MonLvlEx(H)")]), 85 + p["tier"])
            for i in range(1, int(level[self.levels.col("NumMon")]) + 1):
                name = level[self.levels.col(f"nmon{i}")]
                self.assertTrue(name.startswith("rmap_"))
                mon = self.monsters.find(self.monsters.col("Id"), name)
                self.assertEqual(mon[self.monsters.col("MonProp")], f"rmap_{p['item_code']}")
                self.assertEqual(mon[self.monsters.col("TreasureClass(H)")], f"RMap T{p['tier']} Normal")
                self.assertTrue(any(int(mon[self.monsters.col(r + '(H)')] or 0) < 100
                                    for r in ('ResDm', 'ResMa', 'ResFi', 'ResLi', 'ResCo', 'ResPo')))

    def test_only_late_hell_population_gets_entry_wrappers(self):
        found = set()
        for row in self.levels.rows:
            for name, value in zip(self.levels.header, row):
                if value.startswith('rmap_e_'):
                    found.add(row[self.levels.col('Id')])
                    self.assertTrue(name.startswith(('nmon', 'umon')))
        self.assertEqual(found, {'118', '119', '128', '129', '130', '131'})
        for row in self.monsters.rows:
            if row[0].startswith('rmap_e_'):
                for col in ('TreasureClass', 'TreasureClass(N)'):
                    self.assertFalse(row[self.monsters.col(col)].startswith('RMap'))

    def test_recipes_are_hell_only_and_tier_six_cannot_be_upgraded(self):
        table = gen.Table(gen.EXCEL / 'cubemain.txt')
        recipes = [dict(zip(table.header, row)) for row in table.rows if row[0].startswith('rmap ')]
        self.assertEqual(sum(r['description'].startswith('rmap reroll') for r in recipes), 30)
        for r in recipes:
            self.assertEqual(r['min diff'], '2')
            self.assertNotIn('test', r['description'])
            if r['description'].startswith('rmap upgrade'):
                self.assertFalse(r['output'].endswith('6'))

    def test_auras_exist_in_every_difficulty(self):
        skills = gen.Table(gen.EXCEL / 'skills.txt')
        names = {r[skills.col('skill')] for r in skills.rows}
        for a in cfg.AFFIX_PREFIXES + cfg.AFFIX_SUFFIXES:
            if a['kind'] == 'player':
                self.assertIn('rmap_' + a['key'], names)
        for p in self.plans:
            prop = self.props.find(self.props.col('Id'), 'rmap_' + p['item_code'])
            for diff in ('', ' (N)', ' (H)'):
                self.assertEqual(prop[self.props.col('chance1' + diff)], '100')
                self.assertEqual(int(prop[self.props.col('min1' + diff)]), 25 * p['tier'])

    def test_each_boss_room_has_exactly_one_matching_warden(self):
        places = gen.Table(gen.EXCEL / 'monpreset.txt')
        act5 = [r[places.col('Place')] for r in places.rows if r[places.col('Act')] == '5']
        for p in self.plans:
            data = (gen.REPO / 'data/global/tiles/Maps' / (p['item_code'] + '_boss.ds1')).read_bytes()
            offset, rows, w, h = boss_rooms.objects(data)
            mons = [r for r in rows if r[0] == 1]
            self.assertEqual(len(mons), 1)
            self.assertEqual(struct.unpack_from('<I', data, 12)[0], 4)
            self.assertEqual(act5[mons[0][1]], 'rmap_' + p['item_code'] + '_boss')
            mon = self.monsters.find(self.monsters.col('Id'), act5[mons[0][1]])
            self.assertEqual(mon[self.monsters.col('TreasureClass(H)')], f"RMap T{p['tier']} Boss")

    def test_rewards_sustain_and_increase_in_both_banks(self):
        for path in (gen.EXCEL / 'treasureclassex.txt', gen.EXCEL / 'base/treasureclassex.txt'):
            table = gen.Table(path)
            rows = {r[0]: dict(zip(table.header, r)) for r in table.rows}
            last = 1
            for tier in range(1, 7):
                loot = rows[f'RMap T{tier} Loot']
                chance = 42 / (42 + int(loot['NoDrop']))
                self.assertGreater(chance, last if tier > 1 else 0.45)
                last = chance
                boss = rows[f'RMap T{tier} Boss']
                self.assertEqual(boss['Picks'], '-6')
                self.assertEqual(boss['Item2'], f'RMap Tier {min(tier, 5)}')
                self.assertEqual(boss['Item3'], 'RMap Currency')
            for name, row in rows.items():
                if name.startswith('RMap '):
                    self.assertFalse(row['group'])
                    self.assertFalse(any(row[f'Item{i}'].startswith('RMap Tier 6') for i in range(1, 11)))


if __name__ == '__main__':
    unittest.main()
