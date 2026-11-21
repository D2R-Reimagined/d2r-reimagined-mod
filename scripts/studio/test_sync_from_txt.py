"""sync_from_txt: merging an unconverted (TXT) branch into the Studio source."""
import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sync_from_txt as sync
from studio_tables import StudioProject, dumps
from test_studio_tables import _catalog, _table

HEADER = ['Name', 'Id', 'Value']
ROWS = [['alpha', '0', '1'], ['beta', '1', '2'], ['gamma', '2', '3']]
TXT = 'data/global/excel/levels.txt'
BASE_TXT = 'data/global/excel/base/levels.txt'
STR = 'data/local/lng/strings/levels.json'


def tsv(rows):
    return ('\r\n'.join('\t'.join(r) for r in [HEADER] + rows) + '\r\n').encode()


class MergeFromTxtBranch(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix='sync-from-txt-'))
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'core.autocrlf', 'false')
        # The unconverted history: native TXT and string JSON.
        self.write(TXT, tsv(ROWS)); self.write(BASE_TXT, tsv(ROWS))
        self.entries = [{'id': 1, 'Key': 'A', 'enUS': 'a', 'deDE': 'a'}, {'id': 2, 'Key': 'B', 'enUS': 'b', 'deDE': 'b'}]
        self.write(STR, json.dumps(self.entries, indent=4).encode())
        self.commit('txt base')
        self.git('branch', 'next')
        # This branch converts to Studio.
        for p in (TXT, BASE_TXT, STR):
            (self.repo / p).unlink()
        self.write('source/tables/levels.json', dumps(_table(
            'levels', ['global/excel/base/levels.txt', 'global/excel/levels.txt'], HEADER, ROWS)).encode())
        self.write('source/strings/levels.json', dumps(_catalog('local/lng/strings/levels.json', self.entries)).encode())
        self.commit('convert')

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)

    def write(self, rel, data):
        p = self.repo / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)

    def commit(self, msg):
        self.git('add', '-A'); self.git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', msg)

    def on_next(self, fn):
        self.git('checkout', '-q', 'next'); fn(); self.commit('next change'); self.git('checkout', '-q', 'main')

    def edit_studio(self, row, value):
        p = StudioProject(self.repo)
        for t in ('global/excel/levels.txt', 'global/excel/base/levels.txt'):
            header, rows = p.read_table(t); rows[row][2] = value; p.write_table(t, header, rows)
        p.flush()
        self.commit('studio change')

    def run_sync(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = sync.main(['--repo', str(self.repo), *args])
        return code, out.getvalue()

    def test_both_sides_changes_survive(self):
        self.edit_studio(0, '100')                                  # here: alpha
        changed = [r[:] for r in ROWS]; changed[2][2] = '300'       # next: gamma, + new row
        changed.append(['delta', '3', '4'])
        entries = self.entries + [{'id': 3, 'Key': 'C', 'enUS': 'c', 'deDE': 'c'}]
        def change():
            self.write(TXT, tsv(changed)); self.write(BASE_TXT, tsv(changed))
            self.write(STR, json.dumps(entries, indent=4).encode())
        self.on_next(change)
        code, out = self.run_sync('--merge', 'next')
        self.assertEqual(code, 0, out)
        p = StudioProject(self.repo)
        rows = p.read_table('global/excel/levels.txt')[1]
        self.assertEqual(rows, [['alpha', '0', '100'], ['beta', '1', '2'], ['gamma', '2', '300'], ['delta', '3', '4']])
        self.assertEqual(p.read_table('global/excel/base/levels.txt')[1], rows)
        ids = [r['sourceId'] for r in json.loads((self.repo / 'source/tables/levels.json').read_text())['records']]
        self.assertEqual(ids[1], 'row-00001', 'untouched row keeps its id')
        self.assertEqual(p.read_strings('local/lng/strings/levels.json')[-1]['Key'], 'C')
        self.assertEqual(self.run_sync('--merge', 'next', '--check')[0], 0, 'a second run has nothing to do')

    def test_conflict_is_written_out_and_not_applied(self):
        self.edit_studio(1, 'here')
        changed = [r[:] for r in ROWS]; changed[1][2] = 'there'
        self.on_next(lambda: self.write(TXT, tsv(changed)))
        before = (self.repo / 'source/tables/levels.json').read_bytes()
        code, out = self.run_sync('--merge', 'next')
        self.assertEqual(code, 1)
        self.assertIn('CONFLICT', out)
        self.assertEqual((self.repo / 'source/tables/levels.json').read_bytes(), before)
        conflict = (self.repo / '.studio/merge-conflicts' / TXT).read_text()
        self.assertIn('<<<<<<< studio', conflict)

    def test_one_bank_changed_splits_the_table(self):
        changed = [r[:] for r in ROWS]; changed[0][2] = 'rotw'
        self.on_next(lambda: self.write(TXT, tsv(changed)))
        self.assertEqual(self.run_sync('--merge', 'next')[0], 0)
        p = StudioProject(self.repo)
        self.assertEqual(p.read_table('global/excel/levels.txt')[1][0][2], 'rotw')
        self.assertEqual(p.read_table('global/excel/base/levels.txt')[1][0][2], '1')
        self.assertTrue((self.repo / 'source/tables/levels-base.json').exists())

    def test_column_change_is_reported_not_applied(self):
        def change():
            self.write(TXT, ('Name\tId\tValue\tExtra\r\n' + ''.join('\t'.join(r + ['x']) + '\r\n' for r in ROWS)).encode())
        self.on_next(change)
        code, out = self.run_sync('--merge', 'next')
        self.assertIn('columns changed', out)

    def test_tree_mode_applies_a_native_tree(self):
        tree = self.repo / 'export'
        changed = [r[:] for r in ROWS]; changed[2][0] = 'renamed'
        (tree / 'global/excel/base').mkdir(parents=True)
        (tree / 'global/excel/levels.txt').write_bytes(tsv(changed))
        (tree / 'global/excel/base/levels.txt').write_bytes(tsv(changed))
        self.assertEqual(self.run_sync('--tree', str(tree), '--check')[0], 1)
        self.assertEqual(self.run_sync('--tree', str(tree))[0], 0)
        self.assertEqual(StudioProject(self.repo).read_table('global/excel/levels.txt')[1][2][0], 'renamed')
        self.assertEqual(self.run_sync('--tree', str(tree), '--check')[0], 0)


if __name__ == '__main__':
    unittest.main()
