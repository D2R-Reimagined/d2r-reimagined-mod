"""Stage an isolated geometry probe. Does not alter normal generated map data.

Run against the exact installed mod data, then use the matching investigation
DLL. This tests native layout dispatch, portal entry and level IDs above 255.
Wardens, final rewards, preset cleanup and six-tier integration follow only
after those engine assumptions have been tested in game.
"""
import argparse
import hashlib
import json
from pathlib import Path

from generate_maps import Table, set_cells

# key, display, item, future T1 body, stock template, width, height, monsters
LAYOUTS = [
    ('dunes', 'Sunscar Dunes', 'epd', 226, 42, 80, 80,
     ['scarab5', 'sandleaper5', 'vulture4', 'sandraider5']),
    ('highlands', 'Forsaken Highlands', 'eph', 238, 7, 80, 80,
     ['goatman5', 'corruptrogue5', 'cr_archer5', 'quillrat5']),
    ('travincal', 'Fallen Travincal', 'ept', 250, 83, 64, 64,
     ['councilmember3', 'zealot3', 'cantor3', 'vampire4']),
    ('steppes', 'Ashen Steppes', 'eps', 262, 104, 80, 64,
     ['megademon1', 'vilemother1', 'fingermage1', 'regurgitator1']),
    ('infernal', 'Infernal Rift', 'epi', 274, 125, 200, 200,
     ['minion1', 'succubus4', 'overseer1', 'imp5']),
]

def validate_town_boundaries(levels):
    # These appended-map hooks do not relocate campaign Act ranges. A mod that
    # inserts rows between Acts needs the additional DynamicTownLevelIds-style
    # range/table/town patches; silently accepting it would use wrong templates.
    for act, number in enumerate((1, 40, 75, 103, 109)):
        name = f'Act {act + 1} - Town'
        rows = [r for r in levels.rows if r[levels.col('Name')] == name]
        if len(rows) != 1 or (rows[0][levels.col('Id')], rows[0][levels.col('Act')]) != (str(number), str(act)):
            raise ValueError(f'{levels.path}: probe requires unshifted town boundaries; {name} must have Id={number}, Act={act}')

def table_outputs(root):
    outputs = {}
    for bank in ('global/excel', 'global/excel/base'):
        directory = root / bank
        levels, misc, cube, maze, monsters = [Table(directory / (n + '.txt'))
                                            for n in ('levels','misc','cubemain','lvlmaze','monstats')]
        validate_town_boundaries(levels)
        if max(int(r[levels.col('Id')] or 0) for r in levels.rows) != 225:
            raise ValueError('Probe requires the existing five-theme map catalog ending at level 225')
        monster_ids = {r[monsters.col('Id')] for r in monsters.rows}
        sources = {int(r[levels.col('Id')]):r for r in levels.rows if r[levels.col('Id')]}
        for number in range(226, 275):
            row = list(sources[0])
            set_cells(row, levels, {'Name':f'EXTERIOR RESERVED {number}', 'Id':str(number),
                                    'Act':'4', 'DrlgType':'0', 'Waypoint':'255'})
            levels.append(row)
        for count, (key, name, code, number, source, width, height, population) in enumerate(LAYOUTS,1):
            if set(population) - monster_ids:
                raise ValueError(f'{key}: missing monsters {set(population)-monster_ids}')
            row = list(sources[source])
            set_cells(row, levels, {'Name':'EXTERIOR PROBE '+key, 'Id':str(number), 'Act':'4',
                'LevelName':'ExteriorProbe'+key, 'LevelWarp':'ExteriorProbe'+key, 'LevelEntry':'ExteriorProbe'+key,
                'Waypoint':'255', 'Quest':'0', 'QuestFlag':'', 'QuestFlagEx':'', 'SaveMonsters':'1',
                'OffsetX':str(1000 + count*400), 'OffsetY':'1000', 'Depend':'0',
                'SubWaypoint':'-1', 'SubShrine':'-1'})
            for suffix in ('','(N)','(H)'):
                set_cells(row, levels, {'SizeX'+suffix:str(width),'SizeY'+suffix:str(height),
                    'MonDen'+suffix:'400','MonUMin'+suffix:'0','MonUMax'+suffix:'0'})
            # Preserve only the template's authored warp pieces as self-links.
            # The probe asks whether the red portal can locate a spawn room.
            # Final entrance/arena topology must be authored separately.
            for slot in range(8):
                row[levels.col(f'Vis{slot}')] = str(number) if int(row[levels.col(f'Vis{slot}')] or 0) else '0'
            if source==104:
                set_cells(row,levels,{'Vis1':str(number),'Warp1':'69'})
            for stem in ('mon','nmon','umon'):
                for slot in range(1,11):
                    column=f'{stem}{slot}'
                    if column in levels.header:
                        row[levels.col(column)] = population[slot-1] if slot<=len(population) else ''
            row[levels.col('NumMon')]=str(len(population))
            levels.rows[levels.rows.index(levels.find(levels.col('Id'),str(number)))]=row
            if source==125:
                lava=list(maze.find(maze.col('Level'),'125'))
                set_cells(lava,maze,{'Name':'EXTERIOR PROBE infernal','Level':str(number)})
                maze.append(lava)
            if any(r[misc.col('code')]==code for r in misc.rows):
                raise ValueError('Item code collision: '+code)
            item=list(misc.find(misc.col('code'),'md1'))
            set_cells(item,misc,{'name':'ExteriorProbe'+key,'namestr':'ExteriorProbe'+key,
                'code':code,'levelreq':'1','level':'1','spawnable':'0'})
            misc.append(item)
            activate=list(cube.find(cube.col('description'),'rmap activate desert T1'))
            set_cells(activate,cube,{'description':'exterior probe enter '+key,
                'min diff':'0','input 1':code,'output':f'Red Portal,lvl={number},qty=1'})
            cube.append(activate)
            make=cube.blank_row()
            set_cells(make,cube,{'description':'exterior probe create '+key,'enabled':'1','version':'100',
                'numinputs':str(count+1),'input 1':f'tsc,qty={count}', 'input 2':'isc',
                'output':code,'*eol':'0'})
            # Put diagnostic recipes before any broader scroll recipe.
            cube.rows.insert(0,make)
        for table in (levels,misc,cube,maze):
            outputs[Path(bank)/table.path.name] = table.to_bytes()
    for filename in ('levels.json','item-names.json'):
        path=Path('local/lng/strings')/filename
        entries=json.loads((root/path).read_text(encoding='utf-8-sig'))
        next_id=max(e['id'] for e in entries)+1
        for key,name,*_ in LAYOUTS:
            entry={'id':next_id,'Key':'ExteriorProbe'+key}
            entry.update({lang:'TEST - '+name for lang in entries[0] if lang not in ('id','Key')})
            entries.append(entry);next_id+=1
        outputs[path]=(json.dumps(entries,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    return outputs

def stage(root, output):
    outputs=table_outputs(root)
    manifest=[]
    for relative,data in outputs.items():
        target=output/'data'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        manifest.append({'path':relative.as_posix(),
            'original_sha256':hashlib.sha256((root/relative).read_bytes()).hexdigest(),
            'probe_sha256':hashlib.sha256(data).hexdigest()})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    root=args.data_root.resolve();output=args.output.resolve()
    if root==output or root in output.parents or output in root.parents:
        raise SystemExit('Stage must be separate from the source data tree')
    result=stage(root,output)
    print(f'Staged {len(result)} files under {output}; source data unchanged')
