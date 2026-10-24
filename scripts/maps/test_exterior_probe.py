import hashlib
import json
import tempfile
import shutil
import unittest
from pathlib import Path

import exterior_probe as probe
import generate_maps as gen

class ExteriorProbeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Recreate the historical five-theme level baseline in an isolated
        # fixture. The probe deliberately refuses the expanded release catalog.
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        for bank in ('global/excel','global/excel/base'):
            for name in ('levels','misc','cubemain','lvlmaze','monstats'):
                source=gen.REPO/'data'/bank/(name+'.txt')
                target=cls.root/bank/source.name;target.parent.mkdir(parents=True,exist_ok=True)
                if name in ('levels','lvlmaze'):
                    table=gen.Table(source);key=table.col('Id' if name=='levels' else 'Level')
                    table.rows=[r for r in table.rows if not r[key].isdigit() or int(r[key])<=225]
                    target.write_bytes(table.to_bytes())
                else:shutil.copyfile(source,target)
        for name in ('levels.json','item-names.json'):
            rel=Path('local/lng/strings')/name
            (cls.root/rel).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(gen.REPO/'data'/rel,cls.root/rel)
        cls.outputs=probe.table_outputs(cls.root)

    def table(self, bank, name):
        data=self.outputs[Path(bank)/(name+'.txt')].decode().splitlines()
        headings=data[0].split('\t')
        self.assertTrue(all(len(r.split('\t'))==len(headings) for r in data[1:]))
        return [dict(zip(headings,r.split('\t'))) for r in data[1:]]

    def test_existing_levels_unchanged_and_reserved_ids_contiguous(self):
        for bank in ('global/excel','global/excel/base'):
            original=gen.Table(self.root/bank/'levels.txt')
            staged=self.table(bank,'levels')
            self.assertEqual(staged[:len(original.rows)],[dict(zip(original.header,r)) for r in original.rows])
            self.assertEqual([int(r['Id']) for r in staged[len(original.rows):]],list(range(226,275)))
            actual={n for _,_,_,n,*_ in probe.LAYOUTS}
            self.assertTrue(all(r['DrlgType']=='0' for r in staged[len(original.rows):] if int(r['Id']) not in actual))

    def test_themes_keep_distinct_native_layouts_and_population(self):
        for bank in ('global/excel','global/excel/base'):
            levels={int(r['Id']):r for r in self.table(bank,'levels') if r['Id']}
            for key,name,code,number,source,width,height,monsters in probe.LAYOUTS:
                row=levels[number]
                self.assertEqual(row['LevelType'],levels[source]['LevelType'])
                self.assertEqual(row['Act'],'4')
                self.assertEqual(row['DrlgType'],'1' if source==125 else '3')
                self.assertEqual(row['Waypoint'],'255')
                self.assertLess(int(row['Layer']),100)
                for suffix in ('','(N)','(H)'):
                    self.assertEqual((int(row['SizeX'+suffix]),int(row['SizeY'+suffix])),(width,height))
                for stem in ('mon','nmon','umon'):
                    self.assertEqual([row[f'{stem}{i}'] for i in range(1,5)],monsters)
                self.assertTrue(all(row[f'Vis{i}'] in ('0',str(number)) for i in range(8)))

    def test_lava_maze_record_and_spawn_warps(self):
        for bank in ('global/excel','global/excel/base'):
            maze={r['Level']:r for r in self.table(bank,'lvlmaze')}
            self.assertEqual({k:v for k,v in maze['125'].items() if k not in ('Name','Level')},
                             {k:v for k,v in maze['274'].items() if k not in ('Name','Level')})
            levels={int(r['Id']):r for r in self.table(bank,'levels') if r['Id']}
            for number in (226,238,250,262):
                self.assertTrue(any(levels[number][f'Vis{i}']==str(number) and levels[number][f'Warp{i}']!='-1' for i in range(8)))
            self.assertEqual(levels[262]['Warp1'],'69')

    def test_probe_recipes_exercise_ids_above_255_without_joining_drop_pool(self):
        for bank in ('global/excel','global/excel/base'):
            recipes=self.table(bank,'cubemain')
            items={r['code']:r for r in self.table(bank,'misc')}
            for count,(key,name,code,number,*_) in enumerate(probe.LAYOUTS,1):
                # Recipes are prepended individually, so their final order is reversed.
                make=next(r for r in recipes if r['description']=='exterior probe create '+key)
                self.assertEqual(make['input 1'],f'tsc,qty={count}')
                self.assertEqual(make['input 2'],'isc')
                self.assertEqual(make['output'],code)
                enter=next(r for r in recipes if r['description']=='exterior probe enter '+key)
                self.assertEqual(enter['output'],f'Red Portal,lvl={number},qty=1')
                self.assertEqual(items[code]['spawnable'],'0')
            self.assertGreater(probe.LAYOUTS[-1][3],255)

    def test_localized_names_and_deterministic_outputs(self):
        self.assertEqual(self.outputs,probe.table_outputs(self.root))
        for name in ('levels.json','item-names.json'):
            entries=json.loads(self.outputs[Path('local/lng/strings')/name])
            ids=[e['id'] for e in entries]
            self.assertEqual(len(ids),len(set(ids)))
            for key,display,*_ in probe.LAYOUTS:
                item=next(e for e in entries if e['Key']=='ExteriorProbe'+key)
                self.assertEqual(item['enUS'],'TEST - '+display)

    def test_native_policy_contract(self):
        header=(gen.REPO.parent/'d2rl-plugins/plugins/maps-exterior-probe/src/layout_policy.h').read_text()
        for count,(_,name,_,number,source,width,height,_) in enumerate(probe.LAYOUTS,1):
            self.assertIn(f'{{{number}, {source},',header)
            self.assertIn(f'{width}, {height},',header)
            self.assertIn(f'{width}, {height}, {1000+count*400}, 1000,',header)
            self.assertIn('"'+name+'"',header)

    def test_shifted_missing_duplicate_and_wrong_act_towns_are_rejected(self):
        for mutation in ('shifted', 'missing', 'duplicate', 'wrong_act'):
            with self.subTest(mutation=mutation):
                levels=gen.Table(self.root/'global/excel/levels.txt')
                town=levels.find(levels.col('Name'),'Act 2 - Town')
                if mutation=='shifted': town[levels.col('Id')]='138'
                elif mutation=='missing': levels.rows.remove(town)
                elif mutation=='duplicate': levels.append(list(town))
                else: town[levels.col('Act')]='4'
                with self.assertRaisesRegex(ValueError,'unshifted town boundaries'):
                    probe.validate_town_boundaries(levels)

    def test_staging_does_not_modify_source_and_records_rollback_hashes(self):
        before={rel:hashlib.sha256((self.root/rel).read_bytes()).hexdigest() for rel in self.outputs}
        with tempfile.TemporaryDirectory() as temp:
            manifest=probe.stage(self.root,Path(temp))
            self.assertEqual(len(manifest),10)
            for entry in manifest:
                relative=Path(entry['path'])
                self.assertEqual(entry['original_sha256'],before[relative])
                self.assertEqual(entry['probe_sha256'],hashlib.sha256((Path(temp)/'data'/relative).read_bytes()).hexdigest())
                self.assertEqual(before[relative],hashlib.sha256((self.root/relative).read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()
