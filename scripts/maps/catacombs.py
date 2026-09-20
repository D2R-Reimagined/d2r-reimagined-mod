"""Catacombs Warden Plague Pulse: a poison nova cast by the GreaterMummy AI.

Labyrinth bosses cast through stock AIs that use their monstats Skill slots;
`labunraveler` is GreaterMummy AI with `Skill3 = labUnHolyBolt`, `Sk3mode = SC`
and that cast is live-verified. The Catacombs Warden is built on unraveler5
(first Catacombs archetype) so it carries the same AI, and this module swaps
the slot-3 bolt for a map-owned Poison Nova variant at level = tier. Nothing
else is needed: no plugin hook, no aura, no custom cadence. Cast frequency is
the AI's own (aip-driven, roughly every few seconds while a target is near).

The mummy5-based prototypes (native think hook, then an aura) never produced
a nova in-game; the Mummy AI does not read its skill slots at all.
"""

NOVA_SLOT = 3  # GreaterMummy AI casts Skill3 (Resurrect2 and Bestow stay in 1-2).


def generate(api, plans, combat, runtime):
    skills, states, props, monsters = combat
    missiles = api.Table(api.EXCEL / 'missiles.txt')
    missiles.drop_tagged(missiles.col('Missile'), 'rmap_plague_')
    nova = 'rmap_plague_nova'
    row = list(skills.find(skills.col('skill'), 'Poison Nova'))
    api.set_cells(row, skills, {'skill': nova, '*Id': str(len(skills.rows)),
        'charclass': '', 'skilldesc': '', 'reqskill1': '', 'reqlevel': '1',
        'srvmissilea': nova, 'cltmissilea': nova,
        'mana': '0', 'minmana': '0', 'startmana': '0', 'lvlmana': '0',
        'ItemEffect': '', 'ItemCastSound': '',
        'EMin': '64', 'EMax': '80', 'ELen': '75', 'EDmgSymPerCalc': '',
        **{f'E{kind}Lev{i}': '8' for kind in ('Min', 'Max') for i in range(1, 6)}})
    skills.append(row)
    missile = list(missiles.find(missiles.col('Missile'), 'poisonnova'))
    api.set_cells(missile, missiles, {'Missile': nova, '*ID': str(len(missiles.rows)),
        'Skill': nova, 'Range': '18'})
    missiles.append(missile)
    for plan in plans:
        if plan['theme']['key'] != 'catacombs':
            continue
        boss = monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss")
        assert boss[monsters.col('AI')] == 'GreaterMummy', boss[monsters.col('AI')]
        api.set_cells(boss, monsters, {f'Skill{NOVA_SLOT}': nova, f'Sk{NOVA_SLOT}mode': 'SC',
                                       f'Sk{NOVA_SLOT}lvl': str(plan['tier'])})
    return missiles
