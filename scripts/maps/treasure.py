"""Native treasure carriers; occurrence belongs to the maps plugin."""
import json
import maps_config as cfg


def generate(api, monsters, props, stats2, runtime):
    ids, prop_ids = [], []
    next_id = len(api.monster_indices(monsters))
    for tier in cfg.TIERS:
        for spec in cfg.TREASURE_MONSTERS:
            name = f"rmap_treasure_{tier['tier']}_{spec['key']}"
            source = monsters.find(monsters.col('Id'), spec['source'])
            row = list(source)
            marker = list(stats2.find(stats2.col('Id'), source[monsters.col('MonStatsEx')]))
            api.set_cells(marker, stats2, {
                'Id': name, 'automapCel': '305', 'corpseSel': '0', 'revive': '0',
                'ResurrectMode': '', 'ResurrectSkill': '', 'SpawnUniqueMod': '',
                'Utrans': str(spec['palette']), 'Utrans(N)': str(spec['palette']),
                'Utrans(H)': str(spec['palette']),
            })
            stats2.append(marker)
            # An empty, individually owned MonProp row provides a compiled
            # identity anchor. It has no stats or scripted death effects.
            prop = props.blank_row()
            api.set_cells(prop, props, {'Id': name, '*eol': '0'})
            prop_ids.append(len(props.rows))
            props.append(prop)
            ids.append(next_id)
            api.set_cells(row, monsters, {
                'Id': name, '*hcIdx': str(next_id), 'NextInClass': '',
                'NameStr': 'RMapTreasure' + spec['key'], 'MonStatsEx': name, 'MonProp': name,
                'enabled': '1', 'Rarity': '0', 'MinGrp': '1', 'MaxGrp': '1',
                'PartyMin': '0', 'PartyMax': '0', 'spawn': '', 'minion1': '', 'minion2': '',
                'placespawn': '0', 'SetBoss': '0', 'BossXfer': '0', 'sparsePopulate': '0',
                'boss': '0', 'primeevil': '0', 'noRatio': '0', 'DamageRegen': '0',
                'deathDmg': '0', 'CannotDesecrate': '1', 'CannotHerald': '1',
                'TCQuestId': '', 'TCQuestCP': '',
                'SplEndDeath': '', 'SplGetModeChart': '', 'SplEndGeneric': '', 'SplClientEnd': '',
            })
            for i in range(1, 9):
                api.set_cells(row, monsters, {f'Skill{i}': '', f'Sk{i}mode': '', f'Sk{i}lvl': ''})
            for diff in ('', '(N)', '(H)'):
                row[monsters.col('Level' + diff)] = str(cfg.MAP_AREA_LEVEL + tier['tier'] - 1)
                for stem in ('MinHP', 'MaxHP', 'AC', 'Exp', 'A1MinD', 'A1MaxD', 'A1TH',
                             'A2MinD', 'A2MaxD', 'A2TH', 'S1MinD', 'S1MaxD', 'S1TH',
                             'El1MinD', 'El1MaxD', 'El2MinD', 'El2MaxD', 'El3MinD', 'El3MaxD'):
                    target = stem + diff
                    if target not in monsters.header:
                        target = target[0].lower() + target[1:]
                    factor = 1.0 if stem in ('AC', 'Exp', 'A1TH', 'A2TH', 'S1TH') else tier['scale']
                    if stem in ('MinHP', 'MaxHP'):
                        factor *= 4.5  # Three ordinary map monsters' health, below a Warden.
                    row[monsters.col(target)] = str(round(int(source[monsters.col(stem + '(H)')] or 0) * factor))
                for res in ('Dm', 'Ma', 'Fi', 'Li', 'Co', 'Po'):
                    row[monsters.col('Res' + res + diff)] = str(min(75, int(source[monsters.col('Res' + res + '(H)')] or 0)))
            for col in monsters.header:
                if col.startswith('TreasureClass'):
                    row[monsters.col(col)] = 'RMap Treasure ' + spec['key']
            monsters.append(row)
            next_id += 1
            runtime['expansion_models'][name] = spec['source']
    runtime['treasure_ids'] = ids
    runtime['treasure_props'] = prop_ids
    runtime['monster_count'] = next_id
    runtime['prop_count'] = len(props.rows)


def classes(api, table):
    for spec in cfg.TREASURE_MONSTERS:
        row = table.blank_row()
        api.set_cells(row, table, {
            'Treasure Class': 'RMap Treasure ' + spec['key'],
            'Picks': str(-cfg.TREASURE_DROPS), 'NoDrop': '0',
            'Item1': spec['item'], 'Prob1': str(cfg.TREASURE_DROPS),
            'Rare': str(spec['rare']), '*eol': '0',
        })
        table.append(row)


def header(out, runtime):
    out.extend([
        f'inline constexpr uint32_t TreasureTypeCount = {len(cfg.TREASURE_MONSTERS)};',
        f'inline constexpr uint32_t TreasureDefaultChance = {cfg.TREASURE_DEFAULT_CHANCE};',
        f'inline constexpr uint32_t TreasureReleaseChance = {cfg.TREASURE_RELEASE_CHANCE};',
        f'inline constexpr uint32_t TreasureMonsterTableCount = {runtime["monster_count"]};',
        'inline constexpr uint16_t TreasureMonsterIds[] = { ' + ', '.join(map(str, runtime['treasure_ids'])) + ' };',
        'inline constexpr uint16_t TreasureMonProps[] = { ' + ', '.join(map(str, runtime['treasure_props'])) + ' };',
        'inline constexpr const char* TreasureNames[] = { ' + ', '.join(json.dumps(s['name']) for s in cfg.TREASURE_MONSTERS) + ' };',
    ])
