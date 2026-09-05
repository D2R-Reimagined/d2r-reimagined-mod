"""HD asset bindings for every generated monster and map item."""
import json

import maps_config as cfg


def generate(api, plans, monsters):
    path = api.REPO / 'data/hd/character/monsters.json'
    models = json.loads(path.read_text(encoding='utf-8-sig'))
    models = {key: value for key, value in models.items() if not key.startswith('rmap_')}
    sources = {}
    for p in plans:
        codes = cfg.MAP_MONSTERS[p['theme']['key']]
        for i, code in enumerate(codes):
            sources[f"rmap_{p['item_code']}_{i}"] = code
        sources[f"rmap_{p['item_code']}_boss"] = codes[0]
    for row in monsters.rows:
        name = row[monsters.col('Id')]
        if name.startswith('rmap_e_'):
            sources[name] = name.removeprefix('rmap_e_')
    for name, source in sources.items():
        if source not in models:
            raise ValueError(f'No HD monster binding for {source} (used by {name})')
        models[name] = models[source]
    assets = {path: (json.dumps(models, indent=4, ensure_ascii=False) + '\n').encode('utf-8')}
    item_path = api.REPO / 'data/hd/items/items.json'
    items = json.loads(item_path.read_text(encoding='utf-8-sig'))
    codes = {p['item_code'] for p in plans}
    items = [entry for entry in items if not codes.intersection(entry)]
    for p in plans:
        code = p['item_code']
        items.append({code: {'asset': f'map/map_t{code[-1]}'}})
    # Keep the existing compact one-item-per-line formatting.
    lines = ['  ' + json.dumps(entry, separators=(', ', ': ')).replace('{', '{ ').replace('}', ' }')
             for entry in items]
    assets[item_path] = ('[\n' + ',\n'.join(lines) + '\n]\n').encode('utf-8')
    # Reuse a shipped charm ground model; inventory art is tier-specific.
    ground = (api.REPO / 'data/hd/items/misc/charm/charm_sunder.json').read_bytes()
    for tier in range(1, 7):
        assets[api.REPO / f'data/hd/items/misc/map/map_t{tier}.json'] = ground
    return assets
