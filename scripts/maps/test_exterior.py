import unittest
import struct
import json
import re
import generate_maps as gen
import maps_config as cfg
import exterior
import boss_rooms

class ExteriorContract(unittest.TestCase):
    def test_act5_maps_never_use_the_uninitialized_edge_tile_cache(self):
        plans=gen.plan()
        for bank in ('','base/'):
            levels=gen.Table(gen.EXCEL/(bank+'levels.txt'))
            for p in plans:
                for key in ('body_id','boss_id'):
                    row=levels.find(levels.col('Id'),str(p[key]))
                    self.assertEqual(row[levels.col('Act')],'4')
                    self.assertEqual(row[levels.col('DrawEdges')],'0',row[0])
            # Campaign outdoor levels must keep their initialized edge cache.
            for source in (7,42,83):
                row=levels.find(levels.col('Id'),str(source))
                self.assertEqual(row[levels.col('DrawEdges')],'1')

    def test_private_presets_have_matching_hd_and_no_campaign_objects(self):
        table=gen.Table(gen.EXCEL/'lvlprest.txt')
        clones=[dict(zip(table.header,r)) for r in table.rows if r[0].startswith('RMAP Exterior ')]
        self.assertGreater(len(clones),100)
        for row in clones:
            _,_,theme,source,*variant=row['Name'].split()
            original=table.find(table.col('Def'),str(exterior.CLOSED_PRESETS.get((theme,int(source)),int(source))))
            for i in range(1,int(row['Files'])+1):
                rel=row[f'File{i}'].replace('\\','/')
                data=(gen.REPO/'data/global/tiles'/rel).read_bytes()
                self.assertEqual(exterior.objects(data)[1],[])
                self.assertEqual(struct.unpack_from('<I',data,12)[0],4)
                source_rel=original[table.col(f'File{i}')].replace('\\','/')
                hd=gen.REPO/'data/hd/env/preset'/(rel[:-4].lower()+'.json')
                stock_hd=boss_rooms._stock('hd/env/preset/'+source_rel[:-4].lower()+'.json').read_bytes()
                if theme=='travincal' and source=='657':
                    before=json.loads(stock_hd);after=json.loads(hd.read_bytes())
                    self.assertEqual(after['entities'][:-4],before['entities'])
                    for k in before:
                        if k!='entities':self.assertEqual(after[k],before[k])
                    self.assertEqual(len({e['id'] for e in after['entities']}),len(after['entities']))
                    for e in after['entities'][-4:]:
                        self.assertTrue(e['name'].startswith('RMAP_closed_causeway_'))
                        self.assertIn('PhysicsBodyDefinitionComponent',[c['type'] for c in e['components']])
                else:self.assertEqual(hd.read_bytes(),stock_hd)
                self.assertEqual(json.loads(hd.read_bytes())['type'],'Preset')
                # Except for intentional marker edits, all terrain layers stay
                # identical. Every removed object was campaign-owned.
                stock=boss_rooms._stock('global/tiles/'+source_rel).read_bytes()
                if not variant and not (theme=='travincal' and source=='657'):
                    end=exterior.objects(stock)[0]
                    self.assertEqual(data[:12],stock[:12])
                    self.assertEqual(data[16:end],stock[16:end])

    def test_every_exterior_warp_is_scanned_and_has_a_map_destination(self):
        presets=gen.Table(gen.EXCEL/'lvlprest.txt');levels=gen.Table(gen.EXCEL/'levels.txt')
        for row in presets.rows:
            if not row[0].startswith('RMAP Exterior '):continue
            theme=row[0].split()[2]
            for n in range(1,int(row[presets.col('Files')])+1):
                data=(gen.REPO/'data/global/tiles'/row[presets.col(f'File{n}')]).read_bytes()
                for _,_,slot in exterior.warp_markers(data):
                    self.assertEqual(row[presets.col('Scan')],'1',row[0])
                    for p in gen.plan():
                        if p['theme']['key']!=theme:continue
                        body=levels.find(levels.col('Id'),str(p['body_id']))
                        self.assertIn(int(body[levels.col(f'Vis{slot}')]),(p['body_id'],p['boss_id']))
                        self.assertGreaterEqual(int(body[levels.col(f'Warp{slot}')]),0)

    def test_travincal_causeway_is_closed_before_stairs(self):
        data=(gen.REPO/'data/global/tiles/Maps/Exterior/travincal_657_1.ds1').read_bytes()
        width,_,layers,floor,_=exterior.layer_info(data)
        cells,types=layers[0]
        for x in (14,15,16):
            at=4*(24*width+x)
            self.assertEqual(struct.unpack_from('<I',data,cells+at)[0],0x1f00081)
            self.assertEqual(struct.unpack_from('<I',data,types+at)[0],2)
            self.assertTrue(struct.unpack_from('<I',data,floor+at)[0]&0x20000)
        self.assertIn((15,20,6),list(exterior.warp_markers(data)))
        for source in (390,391):
            closed=(gen.REPO/f'data/global/tiles/Maps/Exterior/dunes_{source}_1.ds1').read_bytes()
            self.assertEqual(list(exterior.warp_markers(closed)),[])

    def test_synthetic_markers_never_request_missing_dt1_art(self):
        warps=gen.Table(gen.EXCEL/'lvlwarp.txt')
        hidden=warps.find(warps.col('Id'),'83')
        self.assertEqual(hidden[warps.col('LitVersion')],'0')
        paths=[gen.REPO/'data/global/tiles/Maps/Exterior/travincal_657_1.ds1']
        for path in paths:
            data=path.read_bytes();w,h,layers=exterior.wall_layers(data)
            found=0
            for cells,types in layers:
                for i in range(w*h):
                    cell=struct.unpack_from('<I',data,cells+4*i)[0]
                    kind=struct.unpack_from('<I',data,types+4*i)[0]&255
                    if cell&255 and kind in (10,11) and (cell>>20)&63 in (6,7):
                        self.assertTrue(cell&0x80000000,path.name)
                        found+=1
            self.assertEqual(found,1,path.name)

    def test_warden_exits_are_freestanding_and_match_their_lvlwarp(self):
        # The plugin spawns the exit in the open field. A cliff/border segment
        # there ends its HD plateau at the cell edge (Highlands, 2026-10-01),
        # and a file whose stock warp tile used another lvlwarp gets the wrong
        # click box and exit walk.
        presets=gen.Table(gen.EXCEL/'lvlprest.txt');levels=gen.Table(gen.EXCEL/'levels.txt')
        for theme in cfg.THEMES:
            if not theme.get('exit_preset'):continue
            stock=presets.find(presets.col('Def'),str(theme['exit_preset']))
            self.assertNotRegex(stock[0],r'Cliff|Border',theme['key'])
            exit=presets.find(presets.col('Name'),f"RMAP Exterior {theme['key']} {theme['exit_preset']} exit")
            template=levels.find(levels.col('Id'),str(theme['body_template']))
            # The stock pairing of slot and lvlwarp on this tileset (the
            # template itself may not link the slot, e.g. Outer Steppes).
            campaign=[r for r in levels.rows if r[levels.col('LevelType')]==template[levels.col('LevelType')]
                      and not r[0].startswith(cfg.ROW_TAG)]
            (slot,warp),=theme['body_exits']
            self.assertEqual(slot,7)
            for i in range(1,int(exit[presets.col('Files')])+1):
                source=stock[presets.col(f'File{i}')].replace(chr(92),'/')
                data=boss_rooms._stock('global/tiles/'+source).read_bytes()
                for _,_,s in exterior.warp_markers(data):
                    stock_warps={int(r[levels.col(f'Warp{s}')]) for r in campaign if int(r[levels.col(f'Vis{s}')] or 0)}
                    self.assertEqual(stock_warps,{warp},f"{theme['key']} {source} slot {s}")

    def test_entry_and_warden_markers_are_distinct(self):
        def slots(data):
            w,h,layers=exterior.wall_layers(data)
            return {struct.unpack_from('<I',data,c+4*i)[0]>>20&63
                    for c,t in layers for i in range(w*h)
                    if struct.unpack_from('<I',data,t+4*i)[0]&255 in (10,11)
                    and struct.unpack_from('<I',data,c+4*i)[0]>>20&63<8}
        tiles=gen.REPO/'data/global/tiles/Maps/Exterior'
        for key,source in [('dunes',388),('highlands',52),('steppes',811)]:
            data=(tiles/f'{key}_{source}_1_exit.ds1').read_bytes()
            self.assertEqual(slots(data),{7})
            plain=tiles/f'{key}_{source}_1.ds1'
            if plain.exists():self.assertNotIn(7,slots(plain.read_bytes()))
        self.assertIn(6,slots((tiles/'travincal_657_1.ds1').read_bytes()))
        for variant in (1,2):
            self.assertEqual(slots((tiles/f'infernal_852_{variant}_entry.ds1').read_bytes()),{6})
            self.assertEqual(slots((tiles/f'infernal_852_{variant}_exit.ds1').read_bytes()),{7})

    def test_infernal_rift_is_a_grown_lava_maze_with_real_stairs(self):
        # Abaddon's LevelType 35 routine always builds three rooms; River of
        # Flame's LevelType 28 grows lvlmaze Rooms from the same lava tiles.
        levels=gen.Table(gen.EXCEL/'levels.txt');maze=gen.Table(gen.EXCEL/'lvlmaze.txt')
        presets=gen.Table(gen.EXCEL/'lvlprest.txt');warps=gen.Table(gen.EXCEL/'lvlwarp.txt')
        infernal=[p for p in gen.plan() if p['theme']['key']=='infernal']
        self.assertEqual(len(infernal),6)
        for p in infernal:
            body=levels.find(levels.col('Id'),str(p['body_id']))
            self.assertEqual((body[levels.col('LevelType')],body[levels.col('DrlgType')]),('28','1'))
            self.assertEqual((body[levels.col('Vis6')],body[levels.col('Warp6')]),(str(p['body_id']),'70'))
            self.assertEqual((body[levels.col('Vis7')],body[levels.col('Warp7')]),(str(p['boss_id']),'70'))
            rooms=int(maze.find(maze.col('Level'),str(p['body_id']))[maze.col('Rooms(H)')])
            # The maze's bounding box may span 8x8 24x24 rooms (200x200); at
            # most 32 grown rooms always leaves space for both stairs rooms.
            self.assertEqual(rooms,22+2*(p['tier']-1))
            self.assertLessEqual(rooms,32)
        self.assertEqual(warps.find(warps.col('Id'),'70')[warps.col('Name')],'Act 4 Lava to Mesa')
        stock=presets.find(presets.col('Def'),'852')
        for role,slot in (('entry',6),('exit',7)):
            row=presets.find(presets.col('Name'),f'RMAP Exterior infernal 852 {role}')
            self.assertEqual(row[presets.col('Scan')],'1')
            # River of Flame builds this room with LevelType 28's DT1 list.
            self.assertEqual(row[presets.col('Dt1Mask')],stock[presets.col('Dt1Mask')])
            for n in (1,2):
                data=(gen.REPO/'data/global/tiles'/row[presets.col(f'File{n}')]).read_bytes()
                source=boss_rooms._stock('global/tiles/'+stock[presets.col(f'File{n}')].replace(chr(92),'/')).read_bytes()
                # River of Flame's own stairs: its authored stair art and the
                # warp tile inside it, moved from slot 0. Only that slot
                # field differs from stock; lvlwarp 70 gives the click box.
                markers=list(exterior.warp_markers(data))
                self.assertEqual([m[:2] for m in markers],[m[:2] for m in exterior.warp_markers(source)])
                self.assertEqual([m[2] for m in markers],[slot])
                # 2026-09-29 crash: with no special tile anywhere in the maze
                # the red portal found no room. Only the entry carries
                # Abaddon's hidden landing tile, where these stairs put an
                # arriving player (warp tile + lvlwarp 70 ExitWalk 5,2).
                w,_,layers=exterior.wall_layers(data)
                landings=[(i%w,i//w,struct.unpack_from('<I',data,c+4*i)[0],struct.unpack_from('<I',data,t+4*i)[0])
                          for c,t in layers for i in range(len(data[c:t])//4)
                          if struct.unpack_from('<I',data,t+4*i)[0]&255 in (10,11)
                          and struct.unpack_from('<I',data,c+4*i)[0]>>20&63==exterior.RED_PORTAL_LANDING]
                wx,wy,_=markers[0]
                self.assertEqual(landings,[(wx+1,wy,0x82100081,10)] if role=='entry' else [])
                end=exterior.objects(source)[0]
                changed=sum(data[i]!=source[i] for i in range(16,end))
                self.assertEqual(changed,1 if role=='exit' else 1+sum(b!=0 for b in (0x81,0x00,0x10,0x82,0x0a)))

    def test_native_catalog_and_original_map_ids(self):
        plans=gen.plan()
        self.assertEqual(len(plans),60)
        self.assertEqual([p['item_code'] for p in plans[:30]],
                         [f'm{key}{tier}' for key in 'dkcfw' for tier in range(1,7)])
        self.assertEqual([p['body_id'] for p in plans],list(range(166,286,2)))
        header=(gen.REPO.parent/'d2rl-plugins/plugins/maps/src/map_tables.gen.h').read_text()
        layouts=header.split('ExteriorLayouts[] {')[1].split('};')[0]
        self.assertEqual(len(re.findall(r'\{\d',layouts)),30)
        levels=gen.Table(gen.EXCEL/'levels.txt')
        self.assertEqual([int(levels.find(levels.col('Name'),f'Act {i} - Town')[levels.col('Id')]) for i in range(1,6)], [1,40,75,103,109])
        maze=gen.Table(gen.EXCEL/'lvlmaze.txt')
        for p in plans[30:]:
            body=levels.find(levels.col('Id'),str(p['body_id']))
            self.assertEqual(body[levels.col('Depend')],'0')
            if p['theme']['initializer']:
                self.assertFalse(any(r[maze.col('Level')]==str(p['body_id']) for r in maze.rows))
            else:
                self.assertGreaterEqual(int(maze.find(maze.col('Level'),str(p['body_id']))[maze.col('Rooms')]),22)

if __name__=='__main__':unittest.main()
