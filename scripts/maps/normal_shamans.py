"""Act 1 Normal random Shaman groups; higher difficulties retain stock rows."""

SOURCES = tuple(f'fallenshaman{i}' for i in range(1, 5))
REPLACEMENTS = {source: source + '_normal' for source in SOURCES}


def remove_generated(monsters):
    names = set(REPLACEMENTS.values()) | {'rmap_normal_' + source for source in SOURCES}
    monsters.rows = [row for row in monsters.rows if row[monsters.col('Id')] not in names]


def generate(api, monsters, levels, runtime):
    # Called after all map monsters so existing native monster indices stay put.
    remove_generated(monsters)
    replacements = REPLACEMENTS
    for source, name in replacements.items():
        row = list(monsters.find(monsters.col('Id'), source))
        api.set_cells(row, monsters, {
            'Id': name, '*hcIdx': str(len(monsters.rows)),
            'NextInClass': '', 'MinGrp': '1', 'MaxGrp': '1',
        })
        monsters.append(row)
    for row in levels.rows:
        if row[levels.col('Act')] != '0':
            continue
        for group in ('mon', 'umon'):
            for slot in range(1, 26):
                col = levels.col(f'{group}{slot}')
                source = row[col].removeprefix('rmap_normal_')
                row[col] = replacements.get(source, row[col])
    runtime.setdefault('expansion_models', {}).update(
        {name: source for source, name in replacements.items()})
    runtime['monster_count'] = len(api.monster_indices(monsters))
