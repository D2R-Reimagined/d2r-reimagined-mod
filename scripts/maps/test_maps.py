import unittest
import struct
import json
import re
import generate_maps as gen
import maps_config as cfg
import boss_rooms


def profile_row_name(plan, population, reward, slot):
    """Rewards live in the map's elite table, so they never change a row; a
    population affix replaces only the last slot, with one row per map."""
    last = len(cfg.MAP_MONSTERS[plan['theme']['key']]) - 1
    if population and slot == last:
        return f"rmap_v2_{plan['item_code']}_{population}"
    return f"rmap_{plan['item_code']}_{slot}"


class MappingContract(unittest.TestCase):
    def test_sandswept_arrives_on_stairs_up_and_leaves_by_trapdoor(self):
        # The Lair assigns its Next room first and the portal lands there. The
        # plugin builds that room from the Prev DS1 (stairs up, slot 0) and the
        # Prev room from the Next DS1 (trapdoor, slot 1) into the arena.
        import exterior
        header = gen.DEFAULT_PLUGIN_HEADER.read_text(encoding='utf-8')
        body = header.split('MazePresetSwaps[] {', 1)[1].split('};', 1)[0]
        swaps = {tuple(map(int, s.split(','))) for s in re.findall(r'\{([\d, ]+)\}', body)}
        presets = gen.Table(gen.EXCEL / 'lvlprest.txt')
        for p in self.plans:
            row = self.levels.find(self.levels.col('Id'), str(p['body_id']))
            if p['theme']['key'] != 'desert':
                self.assertFalse(any(s[0] == p['body_id'] for s in swaps))
                continue
            self.assertEqual((row[self.levels.col('Vis0')], row[self.levels.col('Warp0')]), (str(p['body_id']), '48'))
            self.assertEqual((row[self.levels.col('Vis1')], row[self.levels.col('Warp1')]), (str(p['boss_id']), '49'))
            for side, (prev, nxt) in zip('WESN', ((497, 501), (498, 502), (499, 503), (500, 504))):
                self.assertIn((p['body_id'], 18, nxt, prev), swaps)
                self.assertIn((p['body_id'], 18, prev, nxt), swaps)
                for def_id, slot in ((prev, 0), (nxt, 1)):
                    rel = presets.find(presets.col('Def'), str(def_id))[presets.col('File1')]
                    data = boss_rooms._stock(gen.Path('global/tiles') / rel).read_bytes()
                    self.assertEqual({s for _, _, s in exterior.warp_markers(data)}, {slot}, rel)

    def test_map_populations_are_varied_and_fit_the_native_region(self):
        for key, codes in cfg.MAP_MONSTERS.items():
            self.assertGreaterEqual(len(codes), 6, key)
            self.assertLessEqual(len(codes), cfg.MAP_MONSTER_LIMIT, key)
            self.assertNotIn(codes[-1], cfg.EXPANSION_POPULATIONS, key)
        for p in self.plans:
            row = self.levels.find(self.levels.col('Id'), str(p['body_id']))
            self.assertEqual(int(row[self.levels.col('NumMon')]), len(cfg.MAP_MONSTERS[p['theme']['key']]))
        self.assertIn('sandmaggot5', cfg.MAP_MONSTERS['desert'])
        maggot = self.monsters.find(self.monsters.col('Id'), 'rmap_md1_2')
        self.assertEqual(maggot[self.monsters.col('spawn')], 'maggotegg5')

    def test_map_layers_fit_native_automap_directory(self):
        # Live hang: native RVA 0xd5fe0 reads a fixed 0x190-byte directory,
        # then indexes it by Layer. Catacombs T1 layer 112 read stack garbage.
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            levels=gen.Table(bank / 'levels.txt')
            for p in self.plans:
                for role in ('body','boss'):
                    row=levels.find(levels.col('Id'),str(p[role+'_id']))
                    key='body_template' if role=='body' else 'arena_template'
                    template=levels.find(levels.col('Id'),str(p['theme'][key]))
                    layer=int(row[levels.col('Layer')])
                    self.assertGreaterEqual(layer,0)
                    self.assertLess(layer,100)
                    expected=template[levels.col('Layer')]
                    spec=boss_rooms.arena_spec(p['theme'],p['tier'])
                    if role=='boss' and spec.startswith('custom:'):
                        import arenas
                        expected=arenas.LEVEL.get(spec[len('custom:'):],{}).get('Layer',expected)
                    self.assertEqual(layer,int(expected))

    def test_starter_events_own_population_rewards_and_interactive_objects(self):
        import starter_events
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            monsters, stats2, objects, uniques, tcs = [gen.Table(bank / (n + '.txt'))
                for n in ('monstats', 'monstats2', 'objects', 'superuniques', 'treasureclassex')]
            members = [r for r in monsters.rows if r[0].startswith('rmap_event_')]
            self.assertEqual(len(members), 5 * len(self.plans) + 12)
            for row in members:
                marker=stats2.find(stats2.col('Id'), row[monsters.col('MonStatsEx')])
                self.assertEqual(marker[stats2.col('revive')], '0')
                self.assertEqual(row[monsters.col('deathDmg')], '0')
                for diff in ('', '(N)', '(H)'):
                    self.assertIn(int(row[monsters.col('Level'+diff)]), range(100,106))
                if row[0].startswith(('rmap_event_wave_', 'rmap_event_guard_')):
                    for col in monsters.header:
                        if col.startswith('TreasureClass'): self.assertEqual(row[monsters.col(col)], '')
            for name in ('RMapEventSigil','RMapEventCache'):
                obj=objects.find(objects.col('Name'),name)
                self.assertEqual(obj[objects.col('OperateFn')],'6')
                self.assertEqual(obj[objects.col('InitFn')],'0')
                self.assertEqual(obj[objects.col('Lockable')],'0')
                self.assertEqual(obj[objects.col('Selectable2')],'1')
                # Golden quest-chest glow so the object is easy to spot.
                self.assertEqual(obj[objects.col('Overlay')],'1')
            self.assertEqual(len(objects.rows)-len(starter_events.native_rows(objects)),1)
            self.assertEqual(len(uniques.rows)-len(starter_events.native_rows(uniques)),1)
            # Header IDs must be compiled ordinals, never TXT line ordinals or hcIdx.
            native_objects=starter_events.native_rows(objects)
            self.assertEqual([r[objects.col('Name')] for r in native_objects[-2:]],
                             ['RMapEventSigil','RMapEventCache'])
            header=(gen.REPO.parent / 'd2rl-plugins/plugins/maps/src/map_tables.gen.h').read_text()
            def ids(name): return list(map(int,re.search(name+r'\[\] = \{([^}]+)',header)[1].split(',')))
            self.assertEqual([native_objects[i][objects.col('Name')] for i in ids('EventObjectIds')],
                             ['RMapEventSigil','RMapEventCache'])
            native_uniques=starter_events.native_rows(uniques)
            self.assertEqual([native_uniques[i][uniques.col('Superunique')] for i in ids('EventSuperUniqueIds')],
                             [f"rmap_event_challenger_{p['item_code']}" for p in self.plans])
            hc=[r[uniques.col('hcIdx')] for r in uniques.rows if r[uniques.col('hcIdx')]]
            self.assertEqual(len(hc),len(set(hc)))
            for p in self.plans:
                boss=uniques.find(uniques.col('Superunique'),f"rmap_event_challenger_{p['item_code']}")
                for n in range(1,4): self.assertEqual(boss[uniques.col(f'Mod{n}')],'0')
            for tier in range(1,7):
                for kind in ('Raiders','Challenger','Crafting','Equipment','Maps'):
                    tc=tcs.find(tcs.col('Treasure Class'),f'RMap Event {kind} {tier}')
                    self.assertEqual(tc[tcs.col('NoDrop')],'0')
                    self.assertLess(int(tc[tcs.col('Picks')]),0)
                tc=tcs.find(tcs.col('Treasure Class'),f'RMap Event Challenger {tier}')
                self.assertEqual(tc[tcs.col('Item3')],'RMap Currency')
                self.assertEqual(tc[tcs.col('Prob3')],'1')
                tc=tcs.find(tcs.col('Treasure Class'),f'RMap Event Raiders {tier}')
                self.assertEqual([tc[tcs.col(f'Item{i}')] for i in range(1,5)],
                                 [f'RMap T{tier} Loot',f'RMap T{tier} Sustain','RMap Currency','jew'])
            # A nested treasure class only resolves if its row was parsed earlier
            # in the file; the loader otherwise asserts and leaves the slot empty.
            key=tcs.col('Treasure Class')
            defined=set()
            for row in tcs.rows:
                for i in range(1,11):
                    item=row[tcs.col(f'Item{i}')]
                    if item.startswith('RMap '): self.assertIn(item,defined,f"{row[key]} Item{i}")
                defined.add(row[key])

    def test_catacombs_nova_is_cast_from_the_greater_mummy_skill_slot(self):
        import catacombs
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            monsters, skills, missiles, props = [gen.Table(bank / (name + '.txt'))
                for name in ('monstats', 'skills', 'missiles', 'monprop')]
            nova = skills.find(skills.col('skill'), 'rmap_plague_nova')
            self.assertEqual(nova[skills.col('srvdofunc')], '22')
            self.assertEqual(nova[skills.col('srvmissilea')], 'rmap_plague_nova')
            self.assertEqual(nova[skills.col('aura')], '')
            self.assertEqual(nova[skills.col('charclass')], '')
            self.assertEqual(nova[skills.col('ELen')], '75')
            self.assertEqual(nova[skills.col('EDmgSymPerCalc')], '')
            missile = missiles.find(missiles.col('Missile'), 'rmap_plague_nova')
            self.assertEqual(missile[missiles.col('Skill')], 'rmap_plague_nova')
            self.assertEqual(missile[missiles.col('Range')], '18')
            for table, id_col in ((skills, '*Id'), (missiles, '*ID')):
                ids = [row[table.col(id_col)] for row in table.rows if row[table.col(id_col)].isdigit()]
                self.assertEqual(len(ids), len(set(ids)), f'duplicate {id_col} in {bank}')
            self.assertEqual(missiles.find(missiles.col('Missile'), 'poisonnova')[missiles.col('Range')], '30')
            # Same shape as labunraveler: GreaterMummy AI, cast slot 3 in SC.
            lab = monsters.find(monsters.col('Id'), 'labunraveler')
            self.assertEqual((lab[monsters.col('AI')], lab[monsters.col('Sk3mode')]), ('GreaterMummy', 'SC'))
            owners = []
            for row in monsters.rows:
                if not row[0].startswith('rmap_') or not row[0].endswith('_boss'):
                    continue
                uses = [(row[monsters.col(f'Skill{i}')], row[monsters.col(f'Sk{i}mode')], row[monsters.col(f'Sk{i}lvl')]) for i in range(1, 9)]
                if row[0].startswith('rmap_mc'):
                    owners.append(row[0])
                    tier = row[0][7]
                    self.assertEqual(row[monsters.col('AI')], 'GreaterMummy')
                    self.assertEqual(row[monsters.col('BaseId')], 'unraveler1')
                    self.assertEqual(uses[catacombs.NOVA_SLOT - 1], ('rmap_plague_nova', 'SC', tier))
                    self.assertIn(boss_rooms.BOSS_DEATH_SKILL, [u[0] for u in uses])
                    self.assertEqual(row[monsters.col('El1Dur(H)')], '75')
                    prop = props.find(props.col('Id'), row[0])
                    for diff in ('', ' (N)', ' (H)'):
                        for slot in (4, 5, 6):
                            self.assertEqual(prop[props.col(f'prop{slot}{diff}')], '')
                else:
                    self.assertNotIn('rmap_plague_nova', [u[0] for u in uses])
            self.assertEqual(owners, [f'rmap_mc{tier}_boss' for tier in range(1, 7)])

    def test_runtime_monster_ids_use_compiled_order_not_text_line_numbers(self):
        header = (gen.REPO.parent / 'd2rl-plugins/plugins/maps/src/map_tables.gen.h').read_text()
        # Expansion is a TXT section marker, not a native monster record.
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            table = gen.Table(bank / 'monstats.txt')
            names = [row[0] for row in table.rows if row[0].lower() != 'expansion']
            self.assertEqual(len(table.rows) - len(names), 1)
            count = int(re.search(r'TreasureMonsterTableCount = (\d+)', header)[1])
            self.assertEqual(count, len(names))
            wardens = list(map(int, re.search(r'WardenMonsterIds\[\] = \{([^}]+)', header)[1].split(',')))
            self.assertEqual([names[i] for i in wardens], [f"rmap_{p['item_code']}_boss" for p in self.plans])
            ids = list(map(int, re.search(r'TreasureMonsterIds\[\] = \{([^}]+)', header)[1].split(',')))
            self.assertEqual([names[i] for i in ids],
                             [f"rmap_treasure_{tier}_{kind}" for tier in range(1, 7)
                              for kind in ('jewel', 'amulet')])
            body = header.split('PopulationProfiles[][PopulationProfileCount][PopulationSlotCapacity] = {', 1)[1].split('};', 1)[0]
            groups = re.findall(r'\{ ([\d, ]+) \}', body)
            expected = []
            for plan in self.plans:
                for population in range(len(cfg.EXPANSION_POPULATIONS)):
                    for reward in range(len(cfg.EXPANSION_REWARDS)):
                        expected.append([profile_row_name(plan, population, reward, slot)
                            for slot in range(len(cfg.MAP_MONSTERS[plan['theme']['key']]))])
            self.assertEqual([[names[int(i)] for i in group.split(',')] for group in groups], expected)

    def test_treasure_monsters_are_isolated_single_carriers(self):
        models = json.loads((gen.REPO / 'data/hd/character/monsters.json').read_text())
        names = {e['Key']: e['enUS'] for e in gen.load_strings('monsters.json')}
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            monsters, stats2, props, levels = [gen.Table(bank / (n + '.txt'))
                                              for n in ('monstats', 'monstats2', 'monprop', 'levels')]
            carriers = [r for r in monsters.rows if r[monsters.col('Id')].startswith('rmap_treasure_')]
            self.assertEqual(len(carriers), len(cfg.TIERS) * len(cfg.TREASURE_MONSTERS))
            for tier in cfg.TIERS:
                for spec in cfg.TREASURE_MONSTERS:
                    name = f"rmap_treasure_{tier['tier']}_{spec['key']}"
                    row = monsters.find(monsters.col('Id'), name)
                    marker = stats2.find(stats2.col('Id'), name)
                    self.assertEqual(models[name], models[spec['source']])
                    self.assertEqual(names[row[monsters.col('NameStr')]], spec['name'])
                    for field in ('spawn', 'minion1', 'minion2', 'SplEndDeath'):
                        self.assertFalse(row[monsters.col(field)])
                    for i in range(1, 9):
                        self.assertFalse(row[monsters.col(f'Skill{i}')])
                    for field in ('MinGrp', 'MaxGrp', 'CannotHerald', 'CannotDesecrate'):
                        self.assertEqual(row[monsters.col(field)], '1')
                    for field in ('Rarity', 'DamageRegen', 'deathDmg'):
                        self.assertEqual(row[monsters.col(field)], '0')
                    for field in ('corpseSel', 'revive'):
                        self.assertEqual(marker[stats2.col(field)], '0')
                    self.assertEqual(marker[stats2.col('automapCel')], '305')
                    prop = props.find(props.col('Id'), row[monsters.col('MonProp')])
                    for diff in ('', ' (N)', ' (H)'):
                        for i in range(1, 7):
                            self.assertFalse(prop[props.col(f'prop{i}{diff}')])
                    for diff in ('', '(N)', '(H)'):
                        self.assertEqual(int(row[monsters.col('Level' + diff)]), cfg.MAP_AREA_LEVEL + tier['tier'] - 1)
                        for res in ('Dm', 'Ma', 'Fi', 'Li', 'Co', 'Po'):
                            self.assertLessEqual(int(row[monsters.col('Res' + res + diff)]), 75)
                    for field in monsters.header:
                        if field.startswith('TreasureClass'):
                            self.assertEqual(row[monsters.col(field)], 'RMap Treasure ' + spec['key'])
                    self.assertFalse(any(name in level for level in levels.rows))
                    self.assertFalse(any(r[monsters.col(field)] == name for r in monsters.rows
                                         for field in ('spawn', 'minion1', 'minion2')))

    def test_treasure_payout_is_six_direct_items_with_no_sustain(self):
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            table = gen.Table(bank / 'treasureclassex.txt')
            for spec in cfg.TREASURE_MONSTERS:
                row = table.find(table.col('Treasure Class'), 'RMap Treasure ' + spec['key'])
                self.assertEqual(int(row[table.col('Picks')]), -6)
                self.assertEqual(row[table.col('NoDrop')], '0')
                self.assertEqual(row[table.col('Item1')], spec['item'])
                self.assertEqual(row[table.col('Prob1')], '6')
                self.assertEqual(row[table.col('Rare')], str(spec['rare']))
                for field in ('group', 'level', 'Unique', 'Set'):
                    self.assertFalse(row[table.col(field)])
                for i in range(2, 11):
                    self.assertFalse(row[table.col(f'Item{i}')])
                self.assertFalse(any(row[table.col('Treasure Class')] == other[table.col(f'Item{i}')]
                                     for other in table.rows for i in range(1, 11)))

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

    def test_horadric_orb_has_dedicated_hd_sprite_and_ground_binding(self):
        entries = json.loads((gen.REPO / 'data/hd/items/items.json').read_text())
        lookup = {code: value for entry in entries for code, value in entry.items()}
        self.assertEqual(lookup['mor']['asset'], 'powerorbs/horadric_orb')
        ground = gen.REPO / 'data/hd/items/misc/powerorbs/horadric_orb.json'
        definition = json.loads(ground.read_text())
        self.assertTrue(definition['dependencies']['models'])
        itemtypes = gen.Table(gen.EXCEL / 'itemtypes.txt')
        currency = itemtypes.find(itemtypes.col('Code'), 'mcur')
        variants = int(currency[itemtypes.col('VarInvGfx')])
        self.assertEqual(variants, 3)
        # Runtime requests numbered variants 1..VarInvGfx, including orb1.
        # Keep the unnumbered fallback and make every variant visually identical.
        for variant in ('', *(str(i) for i in range(1, variants + 1))):
            for size, suffix in ((98, ''), (49, '.lowend')):
                sprite = gen.REPO / f'data/hd/global/ui/items/misc/powerorbs/horadric_orb{variant}{suffix}.sprite'
                data = sprite.read_bytes()
                fallback = gen.REPO / f'data/hd/global/ui/items/misc/powerorbs/horadric_orb{suffix}.sprite'
                self.assertEqual(data, fallback.read_bytes())
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
            warden = models[f"rmap_{p['item_code']}_boss"]
            self.assertEqual(warden, f"rmap_warden_{models[sources[0]]}")
            model = json.loads((gen.REPO / f'data/hd/character/enemy/{warden}.json').read_text(encoding='utf-8'))
            root = next(e for e in model['entities'] if e['name'] == 'entity_root')
            scale = next(c['scale'] for c in root['components'] if c['type'] == 'TransformDefinitionComponent')
            self.assertGreaterEqual(min(scale.values()), 1.5)
        self.assertEqual(models['rmap_md1_0'], models['clawviper5'])

    @classmethod
    def setUpClass(cls):
        cls.plans = gen.plan()
        cls.levels = gen.Table(gen.EXCEL / "levels.txt")
        cls.monsters = gen.Table(gen.EXCEL / "monstats.txt")
        cls.props = gen.Table(gen.EXCEL / "monprop.txt")
        cls.uniques = gen.Table(gen.EXCEL / "superuniques.txt")

    def test_area_levels_cover_bodies_bosses_and_all_monster_variants(self):
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            levels, monsters = gen.Table(bank / 'levels.txt'), gen.Table(bank / 'monstats.txt')
            for p in self.plans:
                expected = str(99 + p['tier'])
                for lid in (p['body_id'], p['boss_id']):
                    row = levels.find(levels.col('Id'), str(lid))
                    for col in ('MonLvl', 'MonLvl(N)', 'MonLvl(H)',
                                'MonLvlEx', 'MonLvlEx(N)', 'MonLvlEx(H)'):
                        self.assertEqual(row[levels.col(col)], expected)
                population = [row for row in monsters.rows
                              if row[0].startswith(f"rmap_{p['item_code']}_")]
                self.assertTrue(population)
                for row in population:
                    for diff in ('', '(N)', '(H)'):
                        self.assertEqual(row[monsters.col('Level' + diff)], expected, row[0])
            for row in monsters.rows:
                if row[0].startswith('rmap_treasure_'):
                    for diff in ('', '(N)', '(H)'):
                        self.assertEqual(int(row[monsters.col('Level' + diff)]), 99 + int(row[0].split('_')[2]))

    def test_maps_have_independent_combat_population_and_persistent_kills(self):
        for p in self.plans:
            level = self.levels.find(self.levels.col("Id"), str(p["body_id"]))
            self.assertEqual(level[self.levels.col("SaveMonsters")], "1")
            self.assertEqual(int(level[self.levels.col("MonLvlEx(H)")]), 99 + p["tier"])
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
        self.assertEqual(sum(r['description'].startswith('rmap reroll') for r in recipes), 2 * len(self.plans))
        for r in recipes:
            self.assertEqual(r['min diff'], '2')
            self.assertNotIn('test', r['description'])
            if r['description'].startswith('rmap upgrade'):
                self.assertFalse(r['output'].endswith('6'))

    def test_expansion_items_preserve_legacy_activation_and_upgrade_to_new_rolls(self):
        table = gen.Table(gen.EXCEL / 'cubemain.txt')
        recipes = [dict(zip(table.header, row)) for row in table.rows if row[0].startswith('rmap ')]
        misc = gen.Table(gen.EXCEL / 'misc.txt')
        items = {r[misc.col('code')] for r in misc.rows}
        entries = json.loads((gen.REPO / 'data/hd/items/items.json').read_text())
        models = {code: value for entry in entries for code, value in entry.items()}
        for p in self.plans:
            for code in (p['item_code'], cfg.expansion_code(p['item_code'])):
                self.assertIn(code, items)
                self.assertEqual(models[code]['asset'], f"map/map_t{p['tier']}")
                matches = [r for r in recipes if r['input 1'] == code and r['numinputs'] == '1']
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0]['output'], f'"Red Portal,lvl={p["body_id"]},qty=1"')
                rerolls = [r for r in recipes if r['input 1'] == code and r['input 2'] == 'mrl']
                self.assertEqual(len(rerolls), 1)
                self.assertEqual(rerolls[0]['output'], cfg.expansion_code(p['item_code']))

    def test_population_profiles_preserve_native_slots_stats_and_models(self):
        monsters = self.monsters
        lookup = {r[monsters.col('Id')]: r for r in monsters.rows}
        models = json.loads((gen.REPO / 'data/hd/character/monsters.json').read_text())
        for p in self.plans:
            native = cfg.MAP_MONSTERS[p['theme']['key']]
            for population, replacement in enumerate(cfg.EXPANSION_POPULATIONS):
                for reward, reward_name in enumerate(cfg.EXPANSION_REWARDS):
                    if not population and not reward:
                        continue
                    for slot, source in enumerate(native):
                        if replacement and slot == len(native) - 1:
                            source = replacement
                        name = profile_row_name(p, population, reward, slot)
                        row = lookup[name]
                        self.assertEqual(models[name], models[source])
                        self.assertEqual(row[monsters.col('AI')], lookup[source][monsters.col('AI')])
                        self.assertEqual(row[monsters.col('MonProp')], f"rmap_{p['item_code']}")
                        for diff in ('', '(N)', '(H)'):
                            self.assertEqual(row[monsters.col('TreasureClass' + diff)], f"RMap T{p['tier']} Normal")
                            self.assertEqual(row[monsters.col('TreasureClassUnique' + diff)],
                                             f"RMap {p['item_code']} Elite")
                            for res in ('Dm', 'Ma', 'Fi', 'Li', 'Co', 'Po'):
                                self.assertEqual(row[monsters.col('Res' + res + diff)], lookup[source][monsters.col('Res' + res + '(H)')])
                        # No new death-mode skill, resurrection, or offspring;
                        # sand maggots keep only their own native egg laying.
                        self.assertEqual(row[monsters.col('spawn')],
                                         lookup[source][monsters.col('spawn')] if source in cfg.MAP_KEEP_SPAWN else '')
                        for index in range(1, 9):
                            self.assertNotEqual(row[monsters.col(f'Sk{index}mode')], 'DT')

    def test_expansion_rewards_have_one_bonus_attempt_and_unchanged_sustain(self):
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            table = gen.Table(bank / 'treasureclassex.txt')
            classes = {r[0]: dict(zip(table.header, r)) for r in table.rows}
            for tier in range(1, 7):
                boss = classes[f'RMap T{tier} Boss']
                self.assertEqual(boss['Picks'], '-6')
                self.assertEqual(boss['Item2'], f'RMap Tier {min(tier, 5)}')
                for p in (p for p in self.plans if p['tier'] == tier):
                    # Baseline -4 never reaches the bonus; the plugin sets -5
                    # and repoints Item3 for a Gilded/Artificer roll.
                    row = classes[f"RMap {p['item_code']} Elite"]
                    self.assertEqual(row['Picks'], '-4')
                    self.assertEqual((row['Item1'], row['Prob1']), (f'RMap T{tier} Loot', '3'))
                    self.assertEqual((row['Item2'], row['Prob2']), (f'RMap T{tier} Sustain', '1'))
                    self.assertEqual((row['Item3'], row['Prob3']), (f'RMap T{tier} Gilded Bonus', '1'))
                    self.assertFalse(row['Item4'])
                    names = list(classes)
                    for nested in ('Loot', 'Sustain', 'Gilded Bonus', 'Artificer Bonus'):
                        self.assertLess(names.index(f'RMap T{tier} {nested}'), names.index(row['Treasure Class']))
                for reward in ('Gilded', 'Artificer'):
                    bonus = classes[f'RMap T{tier} {reward} Bonus']
                    self.assertEqual(bonus['Picks'], '1')
                    self.assertGreater(int(bonus['NoDrop']), 0)
                    self.assertFalse(any('Sustain' in bonus[f'Item{i}'] or 'Tier 6' in bonus[f'Item{i}'] for i in range(1, 11)))
                if tier <= 5:
                    drops = classes[f'RMap Tier {tier}']
                    self.assertEqual([drops[f'Item{i}'] for i in range(1, len(cfg.THEMES) + 1)],
                                     [cfg.expansion_code(p['item_code']) for p in self.plans if p['tier'] == tier])

    def test_expansion_catalog_excludes_fortified_and_on_death_effects(self):
        self.assertEqual([a['key'] for a in cfg.EXPANSION_AFFIXES],
                         ['bovine', 'coven', 'legion', 'frenzy', 'fire_pact', 'cold_pact', 'light_pact', 'gilded', 'artificer'])
        for a in cfg.EXPANSION_AFFIXES:
            self.assertNotIn('death-skill', [p[0] for p in a.get('monster_props', [])])
            if a['kind'] == 'reward':
                self.assertEqual(a['strength'], 0)

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

    def test_monster_auras_are_clones_on_their_own_states(self):
        # A player's own Conviction/Might/Fanaticism must not share a state
        # with the map monster's copy, or it replaces the monster's stat list.
        header = (gen.REPO.parent / 'd2rl-plugins/plugins/maps/src/map_tables.gen.h').read_text(encoding='utf-8')
        affix_skills = [int(x) for x in header.split('AffixSkills[] = { ')[1].split(' }')[0].split(', ')]
        for bank in (gen.EXCEL, gen.EXCEL / 'base'):
            skills, states = gen.Table(bank / 'skills.txt'), gen.Table(bank / 'states.txt')
            state_names = [r[states.col('state')] for r in states.rows]
            self.assertEqual([r[states.col('*ID')] for r in states.rows],
                             [str(i) for i in range(len(states.rows))])
            for source_name, key in cfg.MONSTER_AURA_CLONES.items():
                source = skills.find(skills.col('skill'), source_name)
                clone = skills.find(skills.col('skill'), key)
                self.assertEqual(clone[skills.col('*Id')], str(skills.rows.index(clone)))
                self.assertEqual(clone[skills.col('charclass')], '')
                for col in ('aurastate', 'auratargetstate'):
                    self.assertTrue(clone[skills.col(col)].startswith(key))
                    self.assertEqual(state_names.count(clone[skills.col(col)]), 1)
                    original = states.find(states.col('state'), source[skills.col(col)])
                    copied = states.find(states.col('state'), clone[skills.col(col)])
                    for c, heading in enumerate(states.header):
                        if heading not in ('state', '*ID'):
                            self.assertEqual(copied[c], original[c], f'{key} {col} {heading}')
                for c, heading in enumerate(skills.header):
                    if heading not in ('skill', '*Id', 'charclass', 'reqskill1', 'reqskill2',
                                       'reqskill3', 'aurastate', 'auratargetstate'):
                        self.assertEqual(clone[c], source[c], f'{key} {heading}')
        for affix, skill in zip(cfg.all_affixes(), affix_skills):
            if affix['kind'] == 'aura':
                self.assertEqual(skills.rows[skill][skills.col('skill')],
                                 cfg.MONSTER_AURA_CLONES[affix['aura_skill']])
        for kit in cfg.WARDENS.values():
            if kit['aura']:
                self.assertNotIn(cfg.monster_aura(kit['aura'][0]), cfg.MONSTER_AURA_CLONES)

    def test_bodies_and_arenas_are_linked_through_their_tileset_warps(self):
        c_id = self.levels.col('Id')
        vis = [self.levels.col(f'Vis{i}') for i in range(8)]
        warp = [self.levels.col(f'Warp{i}') for i in range(8)]
        for p in self.plans:
            theme = p['theme']
            body = self.levels.find(c_id, str(p['body_id']))
            boss = self.levels.find(c_id, str(p['boss_id']))
            template = self.levels.find(c_id, str(theme['body_template']))
            arena = self.levels.find(c_id, str(theme['arena_template']))
            for col in ('LevelType', 'Pal', 'DrlgType'):
                expected = template[self.levels.col(col)]
                if col == 'LevelType' and theme.get('body_level_type'):
                    expected = str(theme['body_level_type'])
                self.assertEqual(body[self.levels.col(col)], expected)
                spec = boss_rooms.arena_spec(theme, p['tier'])
                overrides = {}
                if spec.startswith('custom:'):
                    import arenas
                    overrides = arenas.LEVEL.get(spec[len('custom:'):], {})
                self.assertEqual(boss[self.levels.col(col)], overrides.get(col, arena[self.levels.col(col)]))
            self.assertEqual(body[self.levels.col('DrlgType')], '3' if theme.get('initializer') else '1')
            self.assertEqual(boss[self.levels.col('DrlgType')], '2')
            # Both levels are Act 5 so the Harrogath portal and any town portal
            # taken inside stay in one act, whatever tileset is borrowed.
            self.assertEqual(body[self.levels.col('Act')], '4')
            self.assertEqual(boss[self.levels.col('Act')], '4')
            exits = {(i, int(body[warp[i]])) for i in range(8) if body[vis[i]] == str(p['boss_id'])}
            self.assertEqual(exits, set(theme['body_exits']))
            # The entry stairs are a live warp that points at the body itself:
            # that is what makes the portal land there instead of at the
            # arena stairs. Nothing else may link out of the body.
            entries = {(i, int(body[warp[i]])) for i in range(8) if body[vis[i]] == str(p['body_id'])}
            self.assertEqual(entries, set(theme.get('body_entries', [tuple(theme['body_entry'])])))
            self.assertFalse(any(body[vis[i]] not in ('0', str(p['boss_id']), str(p['body_id']))
                                 for i in range(8)))
            self.assertTrue(all(body[warp[i]] == '-1' for i in range(8) if body[vis[i]] == '0'))
            returns = {(i, int(boss[warp[i]])) for i in range(8) if boss[vis[i]] != '0'}
            self.assertEqual(returns, {tuple(theme['arena_return'])})
            self.assertEqual(boss[vis[theme['arena_return'][0]]], str(p['body_id']))

    def test_themes_use_distinct_tilesets(self):
        c_id = self.levels.col('Id')
        types = [str(t.get('body_level_type') or
                     self.levels.find(c_id, str(t['body_template']))[self.levels.col('LevelType')])
                 for t in cfg.THEMES]
        self.assertEqual(len(set(types)), len(types))

    def test_each_arena_ships_its_hd_preset(self):
        presets = gen.Table(gen.EXCEL / 'lvlprest.txt')
        for p in self.plans:
            preset = presets.find(presets.col('LevelId'), str(p['boss_id']))
            self.assertEqual(preset[presets.col('Files')], '1')
            ds1 = preset[presets.col('File1')]
            self.assertEqual(ds1, f"Maps/{p['item_code']}_boss.ds1")
            hd = gen.REPO / 'data/hd/env/preset/maps' / f"{p['item_code']}_boss.json"
            scene = json.loads(hd.read_text(encoding='utf-8-sig'))
            self.assertEqual(scene['type'], 'Preset')
            _, source_hd = boss_rooms.arena_bytes(gen.REPO, p['theme'], p['tier'])
            self.assertEqual(hd.read_bytes(), source_hd)

    def test_each_boss_room_has_exactly_one_matching_warden(self):
        places = gen.Table(gen.EXCEL / 'monpreset.txt')
        act5 = [r[places.col('Place')] for r in places.rows if r[places.col('Act')] == '5']
        for p in self.plans:
            data = (gen.REPO / 'data/global/tiles/Maps' / (p['item_code'] + '_boss.ds1')).read_bytes()
            offset, rows, w, h = boss_rooms.objects(data)
            mons = [r for r in rows if r[0] == 1]
            self.assertEqual(len(mons), 1)
            self.assertEqual(struct.unpack_from('<I', data, 12)[0], 4)
            self.assertEqual(act5[mons[0][1]], 'rmap_' + p['item_code'] + '_warden')
            unique = self.uniques.find(self.uniques.col('Superunique'), act5[mons[0][1]])
            self.assertEqual(unique[self.uniques.col('Class')], 'rmap_' + p['item_code'] + '_boss')
            self.assertEqual(unique[self.uniques.col('TC(H)')], f"RMap T{p['tier']} Boss")
            mon = self.monsters.find(self.monsters.col('Id'), unique[self.uniques.col('Class')])
            self.assertEqual(mon[self.monsters.col('TreasureClass(H)')], f"RMap T{p['tier']} Boss")

    def test_arena_objects_resolve_in_the_act5_namespace_without_hub_furniture(self):
        objpreset = gen.Table(gen.EXCEL / 'objpreset.txt')
        act5 = {r[objpreset.col('Index')]: r[objpreset.col('ObjectClass')]
                for r in objpreset.rows if r[objpreset.col('Act')] == '5'}
        for p in self.plans:
            source_data, _ = boss_rooms.arena_bytes(gen.REPO, p['theme'], p['tier'])
            source_act = struct.unpack_from('<I', source_data, 12)[0] + 1
            native = {r[objpreset.col('Index')]: r[objpreset.col('ObjectClass')]
                      for r in objpreset.rows if r[objpreset.col('Act')] == str(source_act)}
            _, source_rows, _, _ = boss_rooms.objects(source_data)
            expected = sorted(native[str(r[1])] for r in source_rows
                              if r[0] == 2 and native[str(r[1])] not in boss_rooms.ARENA_EXCLUDED_OBJECTS)
            data = (gen.REPO / 'data/global/tiles/Maps' / (p['item_code'] + '_boss.ds1')).read_bytes()
            _, rows, _, _ = boss_rooms.objects(data)
            # Every kept object is the same class as in the source room, now
            # resolved through Act 5 (the namespace the clone header selects).
            self.assertEqual(sorted(act5[str(r[1])] for r in rows if r[0] == 2), expected, p['item_code'])
            self.assertNotIn('Bank', {act5[str(r[1])] for r in rows if r[0] == 2})
        self.assertEqual(gen.Table(gen.EXCEL / 'base' / 'objpreset.txt').to_bytes(), objpreset.to_bytes())

    def test_custom_arenas_agree_between_room_scene_and_level(self):
        import exterior
        custom = [p for p in self.plans
                  if boss_rooms.arena_spec(p['theme'], p['tier']).startswith('custom:')]
        self.assertEqual({p['theme']['key'] for p in custom}, {'desert', 'frozen', 'worldstone', 'catacombs', 'steppes', 'infernal', 'kurast', 'travincal', 'dunes', 'highlands'})
        presets = gen.Table(gen.EXCEL / 'lvlprest.txt')
        for p in custom:
            ds1, hd = boss_rooms.arena_bytes(gen.REPO, p['theme'], p['tier'])
            width, height = struct.unpack_from('<2I', ds1, 4)
            level = self.levels.find(self.levels.col('Id'), str(p['boss_id']))
            for diff in ('', '(N)', '(H)'):
                self.assertEqual(level[self.levels.col('SizeX' + diff)], str(width))
                self.assertEqual(level[self.levels.col('SizeY' + diff)], str(height))
            preset = presets.find(presets.col('LevelId'), str(p['boss_id']))
            self.assertIn((preset[presets.col('SizeX')], preset[presets.col('SizeY')]),
                          (('0', '0'), (str(width), str(height))))
            # One return warp (a portal tile, or the two tiles of a stairway),
            # on the slot the level links back to the body.
            warps = list(exterior.warp_markers(ds1))
            self.assertIn(len(warps), (1, 2))
            self.assertEqual({slot for _, _, slot in warps}, {p['theme']['arena_return'][0]})
            # The Warden's placeholder and the arrival tile stand on floor.
            cells_x, _, _, floors, _ = exterior.layer_info(ds1)
            floor = lambda x, y: struct.unpack_from('<I', ds1, floors + 4 * (y * cells_x + x))[0]
            _, rows, _, _ = boss_rooms.objects(ds1)
            (warden,) = [r for r in rows if r[0] == 1]
            for x, y in ((warden[2] // 5, warden[3] // 5), warps[0][:2]):
                self.assertEqual(floor(x, y) & 0xff, 0xc2)
            # The HD scene covers the room, stays inside it and loads what it uses.
            scene = json.loads(hd)
            self.assertEqual(scene['biomeFilename'], {'desert': 'data/hd/env/biome/act2_tomb.json',
                                                      'frozen': 'data/hd/env/biome/expansion_icecave.json',
                                                      'worldstone': 'data/hd/env/biome/expansion_baallair.json',
                                                      'catacombs': 'data/hd/env/biome/act1_catacombs.json',
                                                      'steppes': 'data/hd/env/biome/act4_mesa.json',
                                                      'infernal': 'data/hd/env/biome/act4_lava.json',
                                                      'kurast': 'data/hd/env/biome/act3_travincal.json',
                                                      'travincal': 'data/hd/env/biome/act3_travincal_outdoors.json',
                                                      'dunes': 'data/hd/env/biome/act2_outdoors.json',
                                                      'highlands': 'data/hd/env/biome/act1_outdoors.json'}
                             [p['theme']['key']])
            ids = [e['id'] for e in scene['entities']]
            self.assertEqual(len(ids), len(set(ids)))
            scale = next(c for c in scene['terrain']['components'] if 'scale' in c)['scale']
            self.assertAlmostEqual(scale['x'] * 170, (width + 1) * 10)
            self.assertAlmostEqual(scale['z'] * 170, (height + 1) * 10)
            deps = {d['path'].lower() for kind in ('models', 'particles') for d in scene['dependencies'][kind]}
            for entity in scene['entities']:
                for comp in entity['components']:
                    if 'position' in comp:
                        self.assertTrue(0 <= comp['position']['x'] <= (width + 1) * 10, entity['name'])
                        self.assertTrue(0 <= comp['position']['z'] <= (height + 1) * 10, entity['name'])
                    paths = [comp.get('filename')] + [v['filename'] for v in comp.get('variations', [])]
                    for path in filter(None, paths):
                        if path.endswith(('.model', '.particles')):
                            self.assertIn(path.lower(), deps, entity['name'])
                    if comp['type'] == 'PrefabPlacementDefinitionComponent':
                        self.assertTrue((boss_rooms.STOCK_CACHE / comp['prefab'][len('data/'):]).exists(),
                                        comp['prefab'])

    def test_every_warden_has_its_own_marker_row_and_death_portal(self):
        stats2 = gen.Table(gen.EXCEL / 'monstats2.txt')
        skills = gen.Table(gen.EXCEL / 'skills.txt')
        skills.find(skills.col('skill'), boss_rooms.BOSS_DEATH_SKILL)
        for p in self.plans:
            name = 'rmap_' + p['item_code'] + '_boss'
            mon = self.monsters.find(self.monsters.col('Id'), name)
            self.assertEqual(mon[self.monsters.col('MonStatsEx')], name)
            marker = stats2.find(stats2.col('Id'), name)
            self.assertEqual(marker[stats2.col('automapCel')], boss_rooms.BOSS_AUTOMAP_CEL)
            death = [(mon[self.monsters.col(f'Sk{i}mode')], mon[self.monsters.col(f'Sk{i}lvl')])
                     for i in range(1, 9) if mon[self.monsters.col(f'Skill{i}')] == boss_rooms.BOSS_DEATH_SKILL]
            self.assertEqual(death, [('DT', '1')], name)
            # Ordinary map monsters must not inherit either.
            body = self.monsters.find(self.monsters.col('Id'), 'rmap_' + p['item_code'] + '_0')
            self.assertNotEqual(body[self.monsters.col('MonStatsEx')], name)
            self.assertNotIn(boss_rooms.BOSS_DEATH_SKILL,
                             [body[self.monsters.col(f'Skill{i}')] for i in range(1, 9)])

    def test_every_warden_carries_its_theme_kit(self):
        props = gen.Table(gen.EXCEL / 'monprop.txt')
        skills = gen.Table(gen.EXCEL / 'skills.txt')
        sid = lambda name: skills.find(skills.col('skill'), name)[skills.col('*Id')]
        header = (gen.REPO.parent / 'd2rl-plugins/plugins/maps/src/map_tables.gen.h').read_text(encoding='utf-8')
        warden_rows = [int(x) for x in header.split('WardenMonProps[] = { ')[1].split(' }')[0].split(', ')]
        for p, prop_index in zip(self.plans, warden_rows):
            code, tier = p['item_code'], p['tier']
            kit = cfg.WARDENS[p['theme']['key']]
            mon = self.monsters.find(self.monsters.col('Id'), f'rmap_{code}_boss')
            self.assertEqual(mon[self.monsters.col('MonProp')], f'rmap_{code}_boss')
            prop = props.rows[prop_index]
            self.assertEqual(prop[props.col('Id')], f'rmap_{code}_boss')
            for diff in ('', ' (N)', ' (H)'):
                # Slot 1 is the combat-MF aura, 2-3 stay free for the plugin, 4 is the
                # Warden aura and 5-6 are the procs.
                self.assertEqual(prop[props.col(f'prop1{diff}')], 'aura')
                for slot in (2, 3):
                    self.assertEqual(prop[props.col(f'prop{slot}{diff}')], '')
                for slot, kind, key in ((5, 'att-skill', 'on_attack'), (6, 'gethit-skill', 'on_struck')):
                    if kit[key] is None:
                        self.assertEqual(prop[props.col(f'prop{slot}{diff}')], '')
                        continue
                    skill, chance, level = kit[key]
                    self.assertEqual(prop[props.col(f'prop{slot}{diff}')], kind)
                    self.assertEqual(prop[props.col(f'par{slot}{diff}')], sid(skill))
                    self.assertEqual(prop[props.col(f'min{slot}{diff}')], str(chance))
                    self.assertEqual(prop[props.col(f'max{slot}{diff}')],
                                     str(level + cfg.WARDEN_SKILL_PER_TIER * (tier - 1)))
                if kit['aura']:
                    skill, level = kit['aura']
                    slot = cfg.WARDEN_AURA_SLOT
                    self.assertEqual(prop[props.col(f'prop{slot}{diff}')], 'aura')
                    self.assertEqual(prop[props.col(f'par{slot}{diff}')], sid(cfg.monster_aura(skill)))
                    self.assertEqual(prop[props.col(f'max{slot}{diff}')], str(level + cfg.WARDEN_AURA_PER_TIER * (tier - 1)))
                else:
                    self.assertEqual(prop[props.col(f'prop{cfg.WARDEN_AURA_SLOT}{diff}')], '')
            self.assertEqual(mon[self.monsters.col('DamageRegen')], str(cfg.WARDEN_DAMAGE_REGEN))
            self.assertEqual(int(mon[self.monsters.col('MinHP(H)')]),
                             round(cfg.WARDEN_HP_RATIO[0] * 1.5 * p['spec']['scale'] * cfg.WARDEN_HP_MULTIPLIER))
            archetype = self.monsters.find(self.monsters.col('Id'), f'rmap_{code}_0')
            for stem in ('A1MinD(H)', 'A1MaxD(H)', 'A2MinD(H)', 'A2MaxD(H)'):
                base = archetype[self.monsters.col(stem)]
                expected = str(round(int(base) * cfg.WARDEN_DAMAGE_MULTIPLIER)) if base else ''
                self.assertEqual(mon[self.monsters.col(stem)], expected)
            if kit['melee'] and kit['melee'][1]:
                self.assertEqual(mon[self.monsters.col('El1MinD(H)')],
                                 str(round(kit['melee'][1] * cfg.WARDEN_DAMAGE_MULTIPLIER)))
            self.assertNotIn(kit['aura'][0] if kit['aura'] else None,
                             [mon[self.monsters.col(f'Skill{i}')] for i in range(1, 9)])
            archetypes = cfg.MAP_MONSTERS[p['theme']['key']]
            first, second, lo, hi = kit['escort']
            bonus = cfg.WARDEN_ESCORT_PER_TIER * (tier - 1) + (cfg.WARDEN_TIER6_ESCORT_BONUS if tier == 6 else 0)
            self.assertEqual(mon[self.monsters.col('minion1')], f'rmap_{code}_{archetypes.index(first)}')
            self.assertEqual(mon[self.monsters.col('minion2')], f'rmap_{code}_{archetypes.index(second)}')
            self.assertEqual((mon[self.monsters.col('MinGrp')], mon[self.monsters.col('MaxGrp')]), (str(lo + bonus), str(hi + bonus)))
            unique = self.uniques.find(self.uniques.col('Superunique'), f'rmap_{code}_warden')
            self.assertEqual((unique[self.uniques.col('MinGrp')], unique[self.uniques.col('MaxGrp')]), (str(lo + bonus), str(hi + bonus)))
            self.assertEqual(unique[self.uniques.col('Name')], mon[self.monsters.col('NameStr')])
            self.assertEqual(unique[self.uniques.col('AutoPos')], '0')
            for minion in ('minion1', 'minion2'):
                self.monsters.find(self.monsters.col('Id'), mon[self.monsters.col(minion)])
            if kit['melee']:
                self.assertEqual(mon[self.monsters.col('El1Type')], kit['melee'][0])
                self.assertEqual(mon[self.monsters.col('El1Pct(H)')], '100')
            for res in ('Dm', 'Ma', 'Fi', 'Li', 'Co', 'Po'):
                self.assertLessEqual(int(mon[self.monsters.col(f'Res{res}(H)')] or 0), cfg.WARDEN_RESIST_CAP)
            # Ordinary map monsters must not inherit any of it.
            body = self.monsters.find(self.monsters.col('Id'), f'rmap_{code}_0')
            self.assertEqual(body[self.monsters.col('MonProp')], f'rmap_{code}')
            self.assertEqual(body[self.monsters.col('minion1')], '')

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
