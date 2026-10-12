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

import maps_config as cfg

import catacombs
import dunes
import durance
import frozen
import highlands
import infernal
import sandswept
import steppes
import travincal
import worldstone

KITS = (catacombs, infernal, frozen, durance, travincal, sandswept, worldstone, dunes, highlands, steppes)


class Kit:
    def __init__(self, api, skills, missiles, props):
        self.api, self.skills, self.missiles, self.props = api, skills, missiles, props
        self.sources = {}  # cloned missile -> stock missile it copies

    def skill(self, source, name, values):
        """Clone `source` as `name`; returns the clone's skill ID."""
        skills = self.skills
        row = list(skills.find(skills.col('skill'), source))
        next_id = max(int(r[skills.col('*Id')]) for r in skills.rows if r[skills.col('*Id')].isdigit()) + 1
        self.api.set_cells(row, skills, {'skill': name, '*Id': str(next_id),
            'charclass': '', 'skilldesc': '', 'reqskill1': '', 'reqlevel': '1',
            'mana': '0', 'minmana': '0', 'startmana': '0', 'lvlmana': '0',
            'ItemEffect': '', 'ItemCastSound': '', **values})
        skills.append(row)
        return next_id

    def proc(self, boss, skill_id, chance, level):
        """Put an att-skill proc of a kit skill in the Warden's monprop proc
        slot. WARDENS on_attack procs are written by endgame.py before any
        kit skill exists, so a kit that procs its own clone writes it here;
        its WARDENS on_attack stays None and the slot must still be free."""
        props, slot = self.props, cfg.WARDEN_PROC_SLOT
        row = props.find(props.col('Id'), boss)
        for diff in ('', ' (N)', ' (H)'):
            if row[props.col(f'prop{slot}{diff}')]:
                raise ValueError(f'{boss}: monprop slot {slot} is taken')
            self.api.set_cells(row, props, {
                f'prop{slot}{diff}': 'att-skill', f'chance{slot}{diff}': '100',
                f'par{slot}{diff}': str(skill_id), f'min{slot}{diff}': str(chance),
                f'max{slot}{diff}': str(level)})

    def missile(self, source, name, values):
        missiles = self.missiles
        row = list(missiles.find(missiles.col('Missile'), source))
        next_id = max(int(r[missiles.col('*ID')]) for r in missiles.rows if r[missiles.col('*ID')].isdigit()) + 1
        self.api.set_cells(row, missiles, {'Missile': name, '*ID': str(next_id), **values})
        missiles.append(row)
        self.sources[name] = source


def layout(api, monsters, boss, ai, slots, aips, speed=None, aidel=None):
    """Give `boss` the AI, exactly the Skill slots in `slots` ({slot: (skill,
    mode, level)}) and aip1-8 for every difficulty (None keeps the row's
    own). The death portal the boss rooms placed is kept in the slot the
    caller names for it. `speed` (Velocity, Run) and `aidel` override what
    the Warden inherited from its population row (maps_config.AI_PROFILES),
    which already carries the Labyrinth engage distance."""
    cells = {'AI': ai}
    for i in range(1, 9):
        skill, mode, level = slots.get(i, ('', '', ''))
        cells.update({f'Skill{i}': skill, f'Sk{i}mode': mode, f'Sk{i}lvl': str(level)})
    for i, value in enumerate(aips or (), 1):
        cells.update({f'aip{i}{diff}': str(value) for diff in ('', '(N)', '(H)')})
    if speed:
        cells.update({'Velocity': str(speed[0]), 'Run': str(speed[1])})
    if aidel:
        cells.update({f'aidel{diff}': str(aidel) for diff in ('', '(N)', '(H)')})
    api.set_cells(boss, monsters, cells)


# aip slots D2R's monai.txt documents as a delay or interval (frames), by AI.
TIMER_AIPS = {'Summoner': (4, 5), 'ZakarumPriest': (5,), 'HighPriest': (3,),
              'AbyssKnight': (4, 6), 'PinHead': (2, 4), 'CorruptArcher': (3,)}


def paced(frames):
    """A delay or interval in frames at cfg.WARDEN_PACE; blank stays blank."""
    return str(round(int(frames) / cfg.WARDEN_PACE)) if frames else frames


def pace(api, monsters, boss):
    """Run a finished Warden cfg.WARDEN_PACE faster: movement up, AI decision
    delay and documented skill timers down. Called once per Warden after its
    kit, so kit constants stay in their own (unpaced) numbers."""
    col = monsters.col
    cells = {stem: str(round(int(boss[col(stem)] or 0) * cfg.WARDEN_PACE)) for stem in ('Velocity', 'Run')}
    for diff in ('', '(N)', '(H)'):
        cells[f'aidel{diff}'] = paced(boss[col(f'aidel{diff}')])
        for i in TIMER_AIPS.get(boss[col('AI')], ()):
            cells[f'aip{i}{diff}'] = paced(boss[col(f'aip{i}{diff}')])
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
    skills, props, monsters = combat[0], combat[2], combat[-1]
    missiles = api.Table(api.EXCEL / 'missiles.txt')
    missiles.drop_tagged(missiles.col('Missile'), 'rmap_')
    kit = Kit(api, skills, missiles, props)
    for module in KITS:
        module.generate(api, plans, kit, monsters)
    for plan in plans:
        pace(api, monsters, monsters.find(monsters.col('Id'), f"rmap_{plan['item_code']}_boss"))
    return missiles, hd_missiles(api, kit.sources)
