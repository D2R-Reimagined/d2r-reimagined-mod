"""HD asset bindings for every generated monster and map item."""
import json
from pathlib import Path

import boss_rooms
import maps_config as cfg
import normal_shamans

ENEMY_MODELS = Path('hd/character/enemy')


def _scaled_model(api, name, factor):
    """Return a stock monster model scaled by factor at its root entity."""
    source = api.REPO / 'data' / ENEMY_MODELS / f'{name}.json'
    if not source.exists():
        source = boss_rooms._stock(ENEMY_MODELS / f'{name}.json')
    model = json.loads(source.read_text(encoding='utf-8-sig'))
    root = next(e for e in model['entities'] if e['name'] == 'entity_root')
    transform = next((c for c in root['components']
                      if c['type'] == 'TransformDefinitionComponent'), None)
    if transform is None:
        transform = {'type': 'TransformDefinitionComponent',
                     'name': 'entity_root_TransformDefinition',
                     'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                     'orientation': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
                     'scale': {'x': 1.0, 'y': 1.0, 'z': 1.0},
                     'inheritOnlyPosition': False}
        root['components'].append(transform)
    transform['scale'] = {axis: round(value * factor, 4)
                          for axis, value in transform['scale'].items()}
    return (json.dumps(model, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def generate(api, plans, monsters, runtime=None):
    path = api.REPO / 'data/hd/character/monsters.json'
    models = json.loads(path.read_text(encoding='utf-8-sig'))
    models = {key: value for key, value in models.items()
              if not key.startswith('rmap_') and key not in normal_shamans.REPLACEMENTS.values()}
    sources = {}
    for p in plans:
        codes = cfg.MAP_MONSTERS[p['theme']['key']]
        for i, code in enumerate(codes):
            sources[f"rmap_{p['item_code']}_{i}"] = code
        sources[f"rmap_{p['item_code']}_boss"] = cfg.warden_body(p['theme']['key'])
    for row in monsters.rows:
        name = row[monsters.col('Id')]
        if name.startswith('rmap_e_'):
            sources[name] = name.removeprefix('rmap_e_')
    sources.update((runtime or {}).get('expansion_models', {}))
    for name, source in sources.items():
        if source not in models:
            raise ValueError(f'No HD monster binding for {source} (used by {name})')
        models[name] = models[source]
    assets = {}
    # Wardens get an enlarged copy of their archetype's model. A kit's own
    # scale gets its own file, since two themes can share a model.
    for p in plans:
        boss = f"rmap_{p['item_code']}_boss"
        scale = cfg.WARDENS[p['theme']['key']].get('model_scale', cfg.WARDEN_MODEL_SCALE)
        scaled = f'rmap_warden_{models[boss]}'
        if scale != cfg.WARDEN_MODEL_SCALE:
            scaled += f'_x{round(scale * 100)}'
        target = api.REPO / 'data' / ENEMY_MODELS / f'{scaled}.json'
        if target not in assets:
            assets[target] = _scaled_model(api, models[boss], scale)
        models[boss] = scaled
    assets[path] = (json.dumps(models, indent=4, ensure_ascii=False) + '\n').encode('utf-8')
    item_path = api.REPO / 'data/hd/items/items.json'
    items = json.loads(item_path.read_text(encoding='utf-8-sig'))
    codes = {code for p in plans for code in (p['item_code'], cfg.expansion_code(p['item_code']))}
    codes.update(cur['code'] for cur in cfg.CURRENCY)
    items = [entry for entry in items if not codes.intersection(entry)]
    for cur in cfg.CURRENCY:
        items.append({cur['code']: {'asset': cur['asset']}})
    for p in plans:
        code = p['item_code']
        items.append({code: {'asset': f'map/map_t{code[-1]}'}})
        items.append({cfg.expansion_code(code): {'asset': f'map/map_t{code[-1]}'}})
    # Keep the existing compact one-item-per-line formatting.
    lines = ['  ' + json.dumps(entry, separators=(', ', ': ')).replace('{', '{ ').replace('}', ' }')
             for entry in items]
    assets[item_path] = ('[\n' + ',\n'.join(lines) + '\n]\n').encode('utf-8')
    # Reuse a shipped charm ground model; inventory art is tier-specific.
    ground = (api.REPO / 'data/hd/items/misc/charm/charm_sunder.json').read_bytes()
    for tier in range(1, 7):
        assets[api.REPO / f'data/hd/items/misc/map/map_t{tier}.json'] = ground
    return assets
