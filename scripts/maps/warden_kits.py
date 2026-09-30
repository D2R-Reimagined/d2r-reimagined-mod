"""Cast kits for Wardens that run on a stock caster AI.

A Warden with a kit keeps its body but takes a different AI whose monai.txt
documentation names the Skill slots it casts from; the theme module fills
those slots per tier. Every skill and missile is a map-owned clone, and every
cloned missile gets the HD binding of the stock missile it copies: D2R draws a
missile only through hd/missiles/missiles.json, and a clone without an entry
is invisible (the 0.6.0 Plague Pulse).
"""
import json
import re

import catacombs
import infernal

KITS = (catacombs, infernal)


class Kit:
    def __init__(self, api, skills, missiles):
        self.api, self.skills, self.missiles = api, skills, missiles
        self.sources = {}  # cloned missile -> stock missile it copies

    def skill(self, source, name, values):
        skills = self.skills
        row = list(skills.find(skills.col('skill'), source))
        next_id = max(int(r[skills.col('*Id')]) for r in skills.rows if r[skills.col('*Id')].isdigit()) + 1
        self.api.set_cells(row, skills, {'skill': name, '*Id': str(next_id),
            'charclass': '', 'skilldesc': '', 'reqskill1': '', 'reqlevel': '1',
            'mana': '0', 'minmana': '0', 'startmana': '0', 'lvlmana': '0',
            'ItemEffect': '', 'ItemCastSound': '', **values})
        skills.append(row)

    def missile(self, source, name, values):
        missiles = self.missiles
        row = list(missiles.find(missiles.col('Missile'), source))
        next_id = max(int(r[missiles.col('*ID')]) for r in missiles.rows if r[missiles.col('*ID')].isdigit()) + 1
        self.api.set_cells(row, missiles, {'Missile': name, '*ID': str(next_id), **values})
        missiles.append(row)
        self.sources[name] = source


def layout(api, monsters, boss, ai, slots, aips):
    """Give `boss` the AI, exactly the Skill slots in `slots` ({slot: (skill,
    mode, level)}) and aip1-8 for every difficulty. The death portal the
    boss rooms placed is kept in the slot the caller names for it."""
    cells = {'AI': ai}
    for i in range(1, 9):
        skill, mode, level = slots.get(i, ('', '', ''))
        cells.update({f'Skill{i}': skill, f'Sk{i}mode': mode, f'Sk{i}lvl': str(level)})
    for i, value in enumerate(aips, 1):
        cells.update({f'aip{i}{diff}': str(value) for diff in ('', '(N)', '(H)')})
    api.set_cells(boss, monsters, cells)


def death_skill(monsters, boss):
    return next(boss[monsters.col(f'Skill{i}')] for i in range(1, 9)
                if boss[monsters.col(f'Sk{i}mode')] == 'DT')


def hd_key(missile):
    """missiles.json key for a missiles.txt name: lower case, spaces to
    underscores, a trailing number split off (unholybolt2 -> unholybolt_2)."""
    return re.sub(r'(?<=[a-z])(\d+)$', r'_\1', missile.lower().replace(' ', '_'))


def hd_missiles(api, sources):
    """missiles.json with one line per cloned missile, bound to its source's
    particle and placed after the stock Poison Nova entry. Edited as text: a
    JSON round trip reformats the file."""
    path = api.REPO / 'data/hd/missiles/missiles.json'
    text = path.read_bytes().decode('utf-8')
    bindings = json.loads(text.lstrip('﻿'))
    lines = [l for l in text.split('\r\n') if not l.strip().startswith('"rmap_')]
    added = []
    for name, source in sources.items():
        key = hd_key(source)
        if key not in bindings:
            raise ValueError(f'{name}: source missile {source!r} has no HD binding {key!r}')
        added.append(f'    {json.dumps(name)}: {json.dumps(bindings[key])},')
    anchor = next(i for i, l in enumerate(lines) if l.strip().startswith('"poisonnova":'))
    lines[anchor + 1:anchor + 1] = added
    return path, '\r\n'.join(lines).encode('utf-8')


def generate(api, plans, combat):
    """Build every kit. Returns the regenerated missiles table and the HD
    missiles.json asset."""
    skills, monsters = combat[0], combat[-1]
    missiles = api.Table(api.EXCEL / 'missiles.txt')
    missiles.drop_tagged(missiles.col('Missile'), 'rmap_')
    kit = Kit(api, skills, missiles)
    for module in KITS:
        module.generate(api, plans, kit, monsters)
    return missiles, hd_missiles(api, kit.sources)
