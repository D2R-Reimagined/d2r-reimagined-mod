"""Map-owned outdoor presets and the native dispatch metadata.

Campaign assets are never edited. The native preset constructor selects these
copies only when constructing an exterior map body.
"""
import struct
import copy
import json
from pathlib import Path
import boss_rooms
import maps_config as cfg

RANGES = {'dunes': [(364,413)], 'highlands': [(4,51)],
          'travincal': [(653,658)], 'steppes': [(799,827)],
          'infernal': [(836,851),(1053,1058)]}

# These lair mouths carry slot 4, which Dry Hills maps do not link. Use a
# same-size solid mesa (including its HD counterpart), not an orphan warp.
CLOSED_PRESETS = {('dunes',390):398, ('dunes',391):398}

def warp_markers(data):
    width,height,layers=wall_layers(data)
    for cells,types in layers:
        for i in range(width*height):
            cell=struct.unpack_from('<I',data,cells+4*i)[0]
            kind=struct.unpack_from('<I',data,types+4*i)[0]&255
            if cell&255 and kind in (10,11) and (cell>>20)&63<8:
                yield i%width,i//width,(cell>>20)&63

def close_travincal_passage(data):
    """Extend the existing southern terrace across the Kurast causeway.

    Local row 24 is the courtyard edge, before the descending stairs. Main
    index 31/orientation 2 resolves to Kurast/Terraces.dt1, including native
    collision and legacy graphics. The paired HD edit extends that same wall.
    """
    result=bytearray(data)
    width,height,layers,floors,count=layer_info(result)
    if (width,height)!=(33,33):raise ValueError('Travincal passage dimensions changed')
    cells,types=layers[0]
    read=lambda offset,x:struct.unpack_from('<I',result,offset+4*(24*width+x))[0]
    if [(read(cells,x),read(types,x)) for x in (13,14,15,16)] != [
            (0x1f00081,2),(0x1f00081,7),(0,0),(0x1f00081,6)]:
        raise ValueError('Travincal passage wall witness changed')
    for x in (14,15,16):
        at=4*(24*width+x)
        struct.pack_into('<I',result,cells+at,0x1f00081)
        struct.pack_into('<I',result,types+at,2)
        # Also prohibit landing in the closed doorway. Do not change DT1s
        # shared with campaign areas or the interior entry marker at (15,20).
        for layer in range(count):
            offset=floors+layer*width*height*4+at
            value=struct.unpack_from('<I',result,offset)[0]
            if value&255:struct.pack_into('<I',result,offset,value|0x20000)
    return bytes(result)

def close_travincal_hd(data):
    scene=json.loads(data)
    # Authored adjacent segments: preserve model/physics/orientation/height.
    # Each segment is ten HD units (one DS1 tile) long.
    sources={4218006683:(143.0,250.0),2143631721:(143.5,249.5)}
    ids={e['id'] for e in scene['entities']}
    for source,(x,z) in sources.items():
        matches=[e for e in scene['entities'] if e['id']==source]
        if len(matches)!=1:raise ValueError('Travincal HD wall witness changed')
        entity=matches[0]
        transform=next(c for c in entity['components'] if c['type']=='TransformDefinitionComponent')
        if transform['position']!={'x':x,'y':4.898979,'z':z}:
            raise ValueError('Travincal HD wall position changed')
        for shift in (10,20):
            clone=copy.deepcopy(entity)
            identity=0x7f000000+len(ids)
            if identity in ids:raise ValueError('Exterior wall entity ID collision')
            ids.add(identity);clone['id']=identity
            clone['name']=f'RMAP_closed_causeway_{source}_{shift}'
            next(c for c in clone['components'] if c['type']=='TransformDefinitionComponent')['position']['x']+=shift
            scene['entities'].append(clone)
    return (json.dumps(scene,separators=(',',':'))+'\n').encode()

def objects(data):
    version,width,height,_,sub,_=struct.unpack_from('<6I',data)
    _,_,layers,floor_start,floors=layer_info(data)
    offset=floor_start+(width+1)*(height+1)*4*(floors+1+(sub in (1,2)))
    count=struct.unpack_from('<I',data,offset)[0]
    if count>10000 or offset+4+20*count>len(data):raise ValueError('Invalid exterior object block')
    return offset,[struct.unpack_from('<5I',data,offset+4+20*i) for i in range(count)],width,height

def layer_info(data):
    version,width,height,_,_,files=struct.unpack_from('<6I',data)
    if not 10<=version<=18 or width>512 or height>512 or files>100:raise ValueError('Unsupported exterior DS1 header')
    offset=24
    for _ in range(files): offset=data.index(b'\0',offset)+1
    if 9<=version<=13:offset+=8 # legacy editor dimensions, unused by the loader
    walls=struct.unpack_from('<I',data,offset)[0];offset+=4
    floors=1
    if version>=16:floors=struct.unpack_from('<I',data,offset)[0];offset+=4
    if not 0<=walls<=4 or not 1<=floors<=2:raise ValueError('Invalid exterior layer counts')
    size=(width+1)*(height+1)*4
    return width+1,height+1,[(offset+i*size*2,offset+(i*2+1)*size) for i in range(walls)],offset+walls*size*2,floors

def wall_layers(data):return layer_info(data)[:3]

def sanitize(data, *, exit_slot=None, marker=None):
    offset,rows,_,_=objects(data)
    result=bytearray(data[:offset]+struct.pack('<I',0)+data[offset+4+20*len(rows):])
    struct.pack_into('<I',result,12,4)
    width,height,layers=wall_layers(result)
    if exit_slot is not None:
        found=0
        for cells,types in layers:
            for i in range(width*height):
                cell=struct.unpack_from('<I',result,cells+4*i)[0]
                kind=struct.unpack_from('<I',result,types+4*i)[0]&255
                # Orientation 10/11 also serves decorative indexes >=8.
                if kind in (10,11) and ((cell>>20)&63)<8:
                    struct.pack_into('<I',result,cells+4*i,(cell&~0x03f00000)|(exit_slot<<20));found+=1
        if not found: raise ValueError('Entrance preset has no warp markers')
    if marker:
        x,y,slot=marker
        if not (0<x<width-1 and 0<y<height-1):raise ValueError('Warp marker outside interior')
        for cells,types in layers:
            at=(y*width+x)*4
            if struct.unpack_from('<I',result,cells+at)[0]==0:
                # Synthetic landing markers have no matching DT1 wall tile.
                # Bit 31 selects the engine's hidden-warp path; leaving it
                # clear creates a tile with null art and can crash rendering.
                struct.pack_into('<I',result,cells+at,0x80000081|(slot<<20))
                struct.pack_into('<I',result,types+at,10)
                break
        else: raise ValueError(f'Warp marker would overwrite a wall at {x},{y}')
    return bytes(result)

def generate(api,plans,presets,runtime,levels):
    assets={}; mappings=[]; layouts=[]
    next_id=1+max(int(r[presets.col('Def')] or 0) for r in presets.rows)
    stock={int(r[presets.col('Def')]):r for r in presets.rows if r[presets.col('Def')]}
    for theme_index,theme in enumerate(cfg.THEMES):
        if not theme.get('exterior'):continue
        key=theme['key']; exit_id=0
        def clone(source,exit_copy=False):
            nonlocal next_id
            original=stock[CLOSED_PRESETS.get((key,source),source)]
            if any(original[presets.col(c)]!=stock[source][presets.col(c)] for c in ('SizeX','SizeY')):
                raise ValueError('Closed exterior replacement dimensions differ')
            row=list(original); target_id=next_id; next_id+=1
            files=int(row[presets.col('Files')] or 0)
            if not files:raise ValueError(f'Exterior preset {source} has no files')
            api.set_cells(row,presets,{'Name':f'RMAP Exterior {key} {source}'+(' exit' if exit_copy else ''),
                                     'Def':str(target_id),'LevelId':'0'})
            for file_index in range(1,files+1):
                rel=original[presets.col(f'File{file_index}')].replace('\\','/')
                path=boss_rooms._stock(Path('global/tiles')/rel)
                data=path.read_bytes();marker=None
                if key=='travincal' and source==657: marker=(15,20,6)
                if key=='infernal' and 1053<=source<=1056:
                    # File 2 has a consolation chest on the endpoint platform.
                    # Both variants use that same platform; give the two forced
                    # endpoint variants entry/exit warp markers there.
                    chest_rel=original[presets.col('File2')].replace('\\','/')
                    other=boss_rooms._stock(Path('global/tiles')/chest_rel).read_bytes()
                    points=[r for r in objects(other)[1] if r[0]==2 and r[1]==53]
                    if len(points)!=1:raise ValueError(f'{chest_rel}: expected consolation chest')
                    marker=(points[0][2]//5,points[0][3]//5,6 if file_index==1 else 7)
                target=f'Maps/Exterior/{key}_{source}_{file_index}'+('_exit' if exit_copy else '')
                data=sanitize(data,exit_slot=7 if exit_copy else None,marker=marker)
                if key=='travincal' and source==657:data=close_travincal_passage(data)
                if any(warp_markers(data)):row[presets.col('Scan')]='1'
                for _,_,slot in warp_markers(data):
                    for p in plans:
                        if p['theme'] is not theme:continue
                        body=levels.find(levels.col('Id'),str(p['body_id']))
                        if int(body[levels.col(f'Vis{slot}')] or 0) not in (p['body_id'],p['boss_id']) or int(body[levels.col(f'Warp{slot}')] or -1)<0:
                            raise ValueError(f'{target}: unlinked warp slot {slot} in level {p["body_id"]}')
                assets[api.REPO/f'data/global/tiles/{target}.ds1']=data
                hd=boss_rooms._stock(Path('hd/env/preset')/(rel[:-4].lower()+'.json'))
                hd_data=hd.read_bytes()
                if key=='travincal' and source==657:hd_data=close_travincal_hd(hd_data)
                assets[api.REPO/f'data/hd/env/preset/{target.lower()}.json']=hd_data
                row[presets.col(f'File{file_index}')]=target+'.ds1'
            presets.append(row)
            return target_id
        for lo,hi in RANGES[key]:
            for source in range(lo,hi+1):
                if int(stock[source][presets.col('Files')] or 0)>0:
                    mappings.append((theme_index,source,clone(source)))
        if theme.get('exit_preset'):exit_id=clone(theme['exit_preset'],True)
        for p in plans:
            if p['theme'] is not theme:continue
            width,height=theme['body_size']
            layouts.append((p['body_id'],theme['body_template'],
                int(levels.find(levels.col('Id'),str(theme['body_template']))[levels.col('LevelType')]),
                width,height,1400+(p['body_id']-226)*40,1000,theme['initializer'],exit_id,theme_index))
    runtime['exterior_layouts']=layouts;runtime['exterior_presets']=mappings
    return assets

def header(out,runtime):
    out += ['struct ExteriorLayout { uint32_t level, source, type, width, height, x, y; uintptr_t initializer; uint32_t exitPreset, theme; };',
            'inline constexpr ExteriorLayout ExteriorLayouts[] {']
    out += [' {'+', '.join(str(v) for v in r)+'},' for r in runtime['exterior_layouts']]
    out += ['};','struct ExteriorPreset { uint32_t theme, source, replacement; };',
            'inline constexpr ExteriorPreset ExteriorPresets[] {']
    out += [' {'+', '.join(str(v) for v in r)+'},' for r in runtime['exterior_presets']]
    out += ['};']
