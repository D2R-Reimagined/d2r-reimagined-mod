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
                if not variant and not (theme=='travincal' and source=='657') and not (theme=='infernal' and 1053<=int(source)<=1056):
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
        paths += [gen.REPO/f'data/global/tiles/Maps/Exterior/infernal_{source}_{variant}.ds1'
                  for source in range(1053,1057) for variant in (1,2)]
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

    def test_entry_and_warden_markers_are_distinct(self):
        def slots(data):
            w,h,layers=exterior.wall_layers(data)
            return {struct.unpack_from('<I',data,c+4*i)[0]>>20&63
                    for c,t in layers for i in range(w*h)
                    if struct.unpack_from('<I',data,t+4*i)[0]&255 in (10,11)
                    and struct.unpack_from('<I',data,c+4*i)[0]>>20&63<8}
        tiles=gen.REPO/'data/global/tiles/Maps/Exterior'
        for key,source in [('dunes',388),('highlands',24),('steppes',811)]:
            data=(tiles/f'{key}_{source}_1_exit.ds1').read_bytes()
            self.assertEqual(slots(data),{7})
            self.assertNotIn(7,slots((tiles/f'{key}_{source}_1.ds1').read_bytes()))
        self.assertIn(6,slots((tiles/'travincal_657_1.ds1').read_bytes()))
        for source in range(1053,1057):
            self.assertEqual(slots((tiles/f'infernal_{source}_1.ds1').read_bytes()),{6})
            self.assertEqual(slots((tiles/f'infernal_{source}_2.ds1').read_bytes()),{7})

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
                self.assertGreaterEqual(int(maze.find(maze.col('Level'),str(p['body_id']))[maze.col('Rooms')]),24)

if __name__=='__main__':unittest.main()
