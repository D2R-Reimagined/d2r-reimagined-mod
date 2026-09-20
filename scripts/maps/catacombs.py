"""Catacombs-only timed nova data; scheduling belongs to the maps plugin."""
import boss_rooms


def generate(api, plans, combat, runtime):
    skills, states, props, monsters = combat
    missiles = api.Table(api.EXCEL / 'missiles.txt')
    missiles.drop_tagged(missiles.col('Missile'), 'rmap_plague_')
    warning, nova = 'rmap_plague_warning', 'rmap_plague_nova'
    state = states.blank_row()
    api.set_cells(state, states, {'state': warning, '*ID': str(len(states.rows)),
        'green': '1', 'colorpri': '100', 'colorshift': '104',
        'overlay1': 'poisonhit', '*eol': '0'})
    states.append(state)
    tell = skills.blank_row()
    warning_id = len(skills.rows)
    api.set_cells(tell, skills, {'skill': warning, '*Id': str(warning_id),
        'srvdofunc': '18', 'aurastate': warning, 'auralencalc': '50',
        'stsound': 'necromancer_poison_cast', 'range': 'none',
        'anim': 'SC', 'monanim': 'A2', 'InGame': '1', '*eol': '0'})
    skills.append(tell)
    row = list(skills.find(skills.col('skill'), 'Poison Nova'))
    nova_id = len(skills.rows)
    api.set_cells(row, skills, {'skill': nova, '*Id': str(nova_id),
        'charclass': '', 'skilldesc': '', 'reqskill1': '', 'reqlevel': '1',
        'srvmissilea': nova, 'cltmissilea': nova, 'monanim': 'A2',
        'mana': '0', 'minmana': '0', 'startmana': '0', 'interrupt': '1',
        'EMin': '64', 'EMax': '80', 'ELen': '75', 'EDmgSymPerCalc': '',
        **{f'E{kind}Lev{i}': '8' for kind in ('Min', 'Max') for i in range(1, 6)}})
    skills.append(row)
    missile = list(missiles.find(missiles.col('Missile'), 'poisonnova'))
    api.set_cells(missile, missiles, {'Missile': nova, '*ID': str(len(missiles.rows)),
        'Skill': nova, 'Range': '18'})
    missiles.append(missile)
    indices = api.monster_indices(monsters)
    bosses, prop_ids = [], []
    for plan in plans:
        if plan['theme']['key'] != 'catacombs':
            continue
        name = f"rmap_{plan['item_code']}_boss"
        boss = monsters.find(monsters.col('Id'), name)
        boss_rooms.add_skill(api, monsters, boss, warning, 'A2')
        boss_rooms.add_skill(api, monsters, boss, nova, 'A2', plan['tier'])
        bosses.append(indices[name])
        prop_ids.append(next(i for i, row in enumerate(props.rows) if row[props.col('Id')] == name))
    runtime['catacombs'] = (warning_id, nova_id, bosses, prop_ids)
    return missiles


def header(out, runtime):
    warning, nova, bosses, props = runtime['catacombs']
    out.extend([f'inline constexpr uint16_t PlagueWarningSkill = {warning};',
                f'inline constexpr uint16_t PlagueNovaSkill = {nova};',
                'inline constexpr uint16_t CatacombsBossIds[] = { ' + ', '.join(map(str, bosses)) + ' };',
                'inline constexpr uint16_t CatacombsMonProps[] = { ' + ', '.join(map(str, props)) + ' };'])
