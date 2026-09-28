"""Versioned map content, generated from maps_config; no runtime spawning."""
import maps_config as cfg


def generate(api, plans, monsters, props, runtime):
    population_profiles = []
    sources = {}
    compiled_ids = api.monster_indices(monsters)
    next_id = len(compiled_ids)
    import endgame
    for p in plans:
        native = cfg.MAP_MONSTERS[p['theme']['key']]
        last = len(native) - 1
        base = [compiled_ids[f"rmap_{p['item_code']}_{slot}"] for slot in range(len(native))]
        # Reward affixes change no monster: every elite already drops from the
        # map's own table, which the plugin gives the rolled bonus. A
        # population affix replaces only the last slot, so each map gains one
        # row per replacement monster and every other slot keeps its base row.
        replaced = {}
        for population, source in enumerate(cfg.EXPANSION_POPULATIONS):
            if not source:
                continue
            original = monsters.find(monsters.col('Id'), source)
            row = list(original)
            for diff in ('', '(N)', '(H)'):
                row[monsters.col('Level' + diff)] = str(cfg.MAP_AREA_LEVEL + p['tier'] - 1)
                for stem in ('MinHP', 'MaxHP', 'AC', 'Exp', 'A1MinD', 'A1MaxD',
                             'A1TH', 'A2MinD', 'A2MaxD', 'A2TH', 'S1MinD', 'S1MaxD',
                             'S1TH', 'El1MinD', 'El1MaxD', 'El2MinD', 'El2MaxD', 'El3MinD', 'El3MaxD'):
                    target = stem + diff
                    if target not in monsters.header:
                        target = target[0].lower() + target[1:]
                    factor = 1.0 if stem in ('Exp', 'AC', 'A1TH', 'A2TH', 'S1TH') else p['spec']['scale']
                    if stem in ('MinHP', 'MaxHP'):
                        factor *= 1.5
                    row[monsters.col(target)] = str(round(int(original[monsters.col(stem + '(H)')] or 0) * factor))
                for res in ('Dm', 'Ma', 'Fi', 'Li', 'Co', 'Po'):
                    row[monsters.col('Res' + res + diff)] = original[monsters.col('Res' + res + '(H)')]
            name = f"rmap_v2_{p['item_code']}_{population}"
            index = next_id
            next_id += 1
            api.set_cells(row, monsters, {
                'Id': name, '*hcIdx': str(index), 'NextInClass': '',
                'MonProp': f"rmap_{p['item_code']}", 'noAura': '0',
                'noRatio': '0', 'boss': '0', 'primeevil': '0',
                'MinGrp': '3', 'MaxGrp': '5', 'enabled': '1',
                'spawn': '', 'minion1': '', 'minion2': '',
                'TCQuestId': '', 'TCQuestCP': '',
            })
            for diff in ('', '(N)', '(H)'):
                for kind in ('', 'Champ', 'Unique', 'Quest', 'Desecrated',
                             'DesecratedChamp', 'DesecratedUnique', 'Herald'):
                    row[monsters.col('TreasureClass' + kind + diff)] = endgame.monster_class(p, bool(kind))
            monsters.append(row)
            sources[name] = source
            replaced[population] = index
        # Profile shape stays population x reward so rolls index it unchanged.
        population_profiles.append([
            base[:last] + [replaced[population]] if population in replaced else list(base)
            for population in range(len(cfg.EXPANSION_POPULATIONS))
            for _ in cfg.EXPANSION_REWARDS])
    runtime['population_profiles'] = population_profiles
    runtime['expansion_models'] = sources

    properties = api.Table(api.EXCEL / 'properties.txt')
    runtime['property_ids'] = {r[properties.col('code')]: int(r[properties.col('*Id')])
                               for r in properties.rows if r[properties.col('*Id')].isdigit()}
    # A separate probe validates every newly used compiled property code. Never
    # infer the layout from unverified effect IDs in a stale mod/plugin pair.
    codes = ['move2', 'swing2', 'dmg-fire', 'dmg-cold', 'dmg-ltng', 'move2']
    probe = props.blank_row()
    api.set_cells(probe, props, {'Id': 'rmap_expansion_probe', '*eol': '0'})
    runtime['expansion_probe'] = len(props.rows)
    runtime['expansion_probe_properties'] = []
    for slot, code in enumerate(codes, 1):
        values = (runtime['property_ids'][code], slot, 10 + slot, 20 + slot)
        runtime['expansion_probe_properties'].append(values)
        for diff in ('', ' (N)', ' (H)'):
            api.set_cells(probe, props, {f'prop{slot}{diff}': code, f'chance{slot}{diff}': '100',
                                        f'par{slot}{diff}': str(slot), f'min{slot}{diff}': str(10 + slot),
                                        f'max{slot}{diff}': str(20 + slot)})
    props.append(probe)
    runtime['prop_count'] = len(props.rows)


def header(out, plans, runtime):
    legacy_descriptions = [
        'Teeming: increased monster density', 'Swarming: greatly increased density',
        'Storied: more elite packs', 'Legendary: many more elite packs',
        'Sapping: -15% physical attack damage', 'Withering: -30% physical attack damage',
        'Unhallowed: -2 to all skills', 'Conviction', 'Might', 'Fanaticism',
        'Frailty: -30 fire/cold/lightning/poison resistance',
        'Ruin: -60 fire/cold/lightning/poison resistance', 'Agony: -25% physical resistance',
    ]
    import json
    out.extend([
        'enum class AffixKind : uint8_t { World, Player, Aura, Population, Monster, Reward };',
        'struct MonsterEffect { uint32_t code; int32_t parameter, minimum, maximum; };',
        'struct AffixDef {',
        ' const char* display; AffixKind kind; uint8_t strength, minTier, maxTier;',
        ' int16_t densityBonus, rarityBonus; uint16_t propertyId; int16_t propertyValue;',
        ' const char* auraName; uint8_t auraLevel, weight, population, reward, effectCount;',
        ' bool scaleWithTier; MonsterEffect effects[2];',
        '};',
        f'inline constexpr uint32_t LegacyAffixCount = {cfg.LEGACY_AFFIX_COUNT};',
        'inline constexpr AffixDef Affixes[] = {',
    ])
    for i, a in enumerate(cfg.all_affixes()):
        prop = a.get('props', [(None, 0, 0, 0)]) or [(None, 0, 0, 0)]
        effects = a.get('monster_props', [])
        entries = [f'{{ {runtime["property_ids"][code]}, {param}, {lo}, {hi} }}'
                   for code, param, lo, hi in effects]
        entries += ['{}'] * (2 - len(entries))
        fields = [json.dumps(a['display']), 'AffixKind::' + a['kind'].capitalize(),
                  str(a['strength']), str(min(a['tiers'])), str(max(a['tiers'])),
                  str(a.get('density_bonus', 0)), str(a.get('rarity_bonus', 0)),
                  str(runtime['property_ids'].get(prop[0][0], 0)), str(prop[0][2]),
                  json.dumps(a['aura_skill']) if 'aura_skill' in a else 'nullptr',
                  str(a.get('aura_level', 0)), str(a.get('weight', 4 if a['kind'] == 'player' else 10)),
                  str(a.get('population', 0)), str(a.get('reward', 0)), str(len(effects)),
                  'true' if a.get('scale_with_tier') else 'false', '{ ' + ', '.join(entries) + ' }']
        out.append(' { ' + ', '.join(fields) + ' },')
    out.extend(['};', f'inline constexpr uint32_t AffixCount = {len(cfg.all_affixes())};',
                'inline constexpr const char* AffixDescriptions[] = {'])
    for description in legacy_descriptions + [a['description'] for a in cfg.EXPANSION_AFFIXES]:
        out.append(' ' + json.dumps(description) + ',')
    out.extend(['};', 'inline constexpr char ExpansionItemCodes[][5] = { ' + ', '.join(
        json.dumps(cfg.expansion_code(p['item_code'])) for p in plans) + ' };',
        f'inline constexpr uint32_t PopulationProfileCount = {len(cfg.EXPANSION_POPULATIONS) * len(cfg.EXPANSION_REWARDS)};',
        f'inline constexpr uint32_t RewardProfileCount = {len(cfg.EXPANSION_REWARDS)};',
        'inline constexpr uint8_t PopulationSlots[] = { ' + ', '.join(str(len(profiles[0])) for profiles in runtime['population_profiles']) + ' };',
        'inline constexpr bool PopulationAvailable[][4] = { ' + ', '.join(
            '{ ' + ', '.join('true' if replacement is None or replacement != cfg.MAP_MONSTERS[p['theme']['key']][-1] else 'false'
                             for replacement in cfg.EXPANSION_POPULATIONS) + ' }' for p in plans) + ' };',
        f'inline constexpr uint32_t PopulationSlotCapacity = {cfg.MAP_MONSTER_LIMIT};',
        'inline constexpr uint16_t PopulationProfiles[][PopulationProfileCount][PopulationSlotCapacity] = {'])
    for profiles in runtime['population_profiles']:
        out.append(' { ' + ', '.join('{ ' + ', '.join(map(str, ids)) + ' }' for ids in profiles) + ' },')
    import endgame
    out.extend(['};',
        '// Reward affixes: the map\'s elite table is Picks -4 over [Loot x3,',
        '// Sustain x1, <bonus> x1]; reward r sets Picks -5 and the third entry',
        '// to RewardBonusClasses[tier-1][r-1]. Names are TXT Treasure Class keys.',
        'struct RewardClass { const char* elite; const char* loot; const char* sustain; };',
        'inline constexpr RewardClass RewardClasses[] = {'])
    out.extend(f' {{ "{endgame.elite_class(p)}", "RMap T{p["tier"]} Loot", "RMap T{p["tier"]} Sustain" }},'
               for p in plans)
    out.extend(['};', 'inline constexpr const char* RewardBonusClasses[][2] = {'])
    out.extend(f' {{ "RMap T{tier} Gilded Bonus", "RMap T{tier} Artificer Bonus" }},'
               for tier in range(1, len(cfg.TIERS) + 1))
    out.extend(['};', f'inline constexpr uint32_t ExpansionPropertyProbe = {runtime["expansion_probe"]};',
                'inline constexpr MonsterEffect ExpansionProbeProperties[] = {'])
    out.extend(' { ' + ', '.join(map(str, values)) + ' },' for values in runtime['expansion_probe_properties'])
    out.append('};')
    for index, affix in enumerate(cfg.all_affixes()):
        out.append(f'inline constexpr uint8_t Affix_{affix["key"]} = {index};')
