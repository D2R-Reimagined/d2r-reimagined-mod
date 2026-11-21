"""Tests for studio_tables: lossless mapping between Mod Studio files and native shapes.

Run from scripts/studio:  python -m unittest test_studio_tables
STUDIO_PROJECT=<path> also round-trips every table and catalog of that project
(defaults to the repository root when it is a Mod Studio project).
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from studio_tables import StudioProject, dumps

REPO = Path(__file__).resolve().parents[2]


def _table(name, targets, header, rows):
    return {
        'schema': {
            'schemaVersion': 1, 'name': name, 'targets': targets, 'identityColumns': [],
            'columns': [{'key': h, 'header': h} for h in header],
            'bom': False, 'newline': '\r\n', 'finalNewline': True,
        },
        'records': [
            {'sourceId': f'row-{i:05d}', 'order': i, 'columnCount': len(r),
             'fields': {h: v for h, v in zip(header, r) if v}}
            for i, r in enumerate(rows)
        ],
    }


def _catalog(target, entries, locales=('enUS', 'deDE')):
    return {
        'schema': {'schemaVersion': 1, 'category': Path(target).stem, 'target': target,
                   'locales': list(locales), 'bom': False, 'newline': '\r\n',
                   'finalNewline': True, 'indent': 4},
        'records': [
            {'order': i, 'id': e['id'], 'Key': e['Key'],
             'translations': {l: e[l] for l in locales if l in e}}
            for i, e in enumerate(entries)
        ],
    }


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='studio-tables-'))
        (self.root / 'source/tables').mkdir(parents=True)
        (self.root / 'source/strings').mkdir(parents=True)
        self.header = ['Name', 'Id', 'Value']
        self.rows = [['alpha', '0', '1'], ['beta', '1', ''], ['gamma', '2', '3']]
        self.write('source/tables/levels.json', _table(
            'levels', ['global/excel/base/levels.txt', 'global/excel/levels.txt'], self.header, self.rows))
        self.write('source/strings/levels.json', _catalog(
            'local/lng/strings/levels.json', [{'id': 1, 'Key': 'A', 'enUS': 'a', 'deDE': 'ä'}]))

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, doc):
        (self.root / rel).write_text(dumps(doc), encoding='utf-8')

    def load(self, rel):
        return json.loads((self.root / rel).read_text(encoding='utf-8'))

    def ids(self, rel):
        return [r['sourceId'] for r in self.load(rel)['records']]


class TableTests(Fixture):
    def test_reads_native_shape(self):
        p = StudioProject(self.root)
        self.assertEqual(p.read_table('global/excel/levels.txt'), (self.header, self.rows))
        self.assertEqual(p.native_bytes('global/excel/base/levels.txt'),
                         b'Name\tId\tValue\r\nalpha\t0\t1\r\nbeta\t1\t\r\ngamma\t2\t3\r\n')

    def test_target_of_accepts_native_paths(self):
        self.assertEqual(StudioProject.target_of(r'C:\mod\data\global\excel\base\levels.txt'), 'global/excel/base/levels.txt')
        self.assertEqual(StudioProject.target_of('data/local/lng/strings/levels.json'), 'local/lng/strings/levels.json')

    def test_unchanged_write_is_a_no_op(self):
        p = StudioProject(self.root)
        for t in p.table_targets():
            p.write_table(t, *p.read_table(t))
        self.assertEqual(p.check(), [])
        self.assertEqual(p.flush(), [])

    def test_inserted_row_keeps_ids_of_rows_after_it(self):
        p = StudioProject(self.root)
        rows = self.rows[:1] + [['new', '9', '9']] + self.rows[1:]
        for t in ('global/excel/levels.txt', 'global/excel/base/levels.txt'):
            p.write_table(t, self.header, rows)
        p.flush()
        ids = self.ids('source/tables/levels.json')
        self.assertEqual(ids[0], 'row-00000')
        self.assertTrue(ids[1].startswith('gen-'))
        self.assertEqual(ids[2:], ['row-00001', 'row-00002'])
        self.assertEqual([r['order'] for r in self.load('source/tables/levels.json')['records']], [0, 1, 2, 3])

    def test_new_ids_are_deterministic(self):
        rows = self.rows + [['dup', '7', ''], ['dup', '7', '']]
        results = []
        for _ in range(2):
            self.setUp()
            p = StudioProject(self.root)
            for t in p.table_targets():
                p.write_table(t, self.header, rows)
            p.flush()
            results.append(self.ids('source/tables/levels.json'))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(set(results[0])), len(rows), 'duplicate rows get distinct ids')

    def test_diverging_banks_split_and_converge_back(self):
        p = StudioProject(self.root)
        changed = [r[:] for r in self.rows]; changed[2][2] = '30'
        p.write_table('global/excel/levels.txt', self.header, changed)
        p.flush()
        top, base = self.load('source/tables/levels.json'), self.load('source/tables/levels-base.json')
        self.assertEqual(top['schema']['targets'], ['global/excel/levels.txt'])
        self.assertEqual(base['schema']['targets'], ['global/excel/base/levels.txt'])
        self.assertEqual(base['schema']['name'], 'levels-base')
        self.assertEqual([r['sourceId'] for r in base['records']], ['row-00000', 'row-00001', 'row-00002'])
        self.assertEqual([r['sourceId'] for r in top['records']][:2], ['row-00000', 'row-00001'])
        p = StudioProject(self.root)
        self.assertEqual(p.read_table('global/excel/base/levels.txt')[1], self.rows)
        p.write_table('global/excel/base/levels.txt', self.header, changed)
        p.flush()
        self.assertFalse((self.root / 'source/tables/levels-base.json').exists())
        merged = self.load('source/tables/levels.json')
        self.assertEqual(merged['schema']['targets'], ['global/excel/base/levels.txt', 'global/excel/levels.txt'])
        self.assertEqual(StudioProject(self.root).read_table('global/excel/base/levels.txt')[1], changed)

    def test_rejects_header_changes_and_bad_cells(self):
        p = StudioProject(self.root)
        with self.assertRaises(ValueError):
            p.write_table('global/excel/levels.txt', ['Name', 'Id'], [])
        with self.assertRaises(ValueError):
            p.write_table('global/excel/levels.txt', self.header, [['a\tb', '', '']])

    def test_staged_writes_are_read_back_before_flush(self):
        p = StudioProject(self.root)
        p.write_table('global/excel/levels.txt', self.header, self.rows[:1])
        self.assertEqual(p.read_table('global/excel/levels.txt')[1], self.rows[:1])
        self.assertEqual(len(StudioProject(self.root).read_table('global/excel/levels.txt')[1]), 3)


class StringTests(Fixture):
    def test_round_trip_and_new_entries(self):
        p = StudioProject(self.root)
        target = 'local/lng/strings/levels.json'
        entries = p.read_strings(target)
        self.assertEqual(entries, [{'id': 1, 'Key': 'A', 'enUS': 'a', 'deDE': 'ä'}])
        p.write_strings(target, entries)
        self.assertEqual(p.check(), [])
        entries.append({'id': 2, 'Key': 'B', 'enUS': 'b', 'deDE': None})
        p.write_strings(target, entries)
        p.flush()
        recs = self.load('source/strings/levels.json')['records']
        self.assertNotIn('sourceId', recs[0], 'imported entries stay imported')
        self.assertTrue(recs[1]['sourceId'].startswith('str-'))
        self.assertEqual(recs[1]['nullTranslations'], ['deDE'])
        self.assertEqual(StudioProject(self.root).read_strings(target)[1], entries[1])

    def test_rejects_unknown_locale(self):
        p = StudioProject(self.root)
        with self.assertRaises(ValueError):
            p.write_strings('local/lng/strings/levels.json', [{'id': 1, 'Key': 'A', 'xxXX': 'a'}])


class EscapingTests(unittest.TestCase):
    def test_matches_system_text_json_relaxed(self):
        self.assertEqual(dumps('a"b\\c\n\u00a0 \u200c<>&\U0001F600\x7f'),
                         '"a\\"b\\\\c\\n\\u00A0 \u200c<>&\\uD83D\\uDE00\\u007F"\n')


@unittest.skipUnless((Path(os.environ.get('STUDIO_PROJECT', REPO)) / 'source/tables').is_dir()
                     and any((Path(os.environ.get('STUDIO_PROJECT', REPO)) / 'source/tables').glob('*.json')),
                     'no Mod Studio project to round-trip')
class ProjectRoundTrip(unittest.TestCase):
    """Every table and catalog of the real project survives read -> write unchanged."""

    def test_every_file_round_trips(self):
        root = Path(os.environ.get('STUDIO_PROJECT', REPO))
        p = StudioProject(root)
        for t in p.table_targets():
            p.write_table(t, *p.read_table(t))
        for target in list(p._catalogs):
            p.write_strings(target, p.read_strings(target))
        self.assertEqual(p.check(), [])

    def test_files_are_written_in_studio_format(self):
        root = Path(os.environ.get('STUDIO_PROJECT', REPO))
        for f in sorted((root / 'source').glob('*/*.json')):
            raw = f.read_bytes().decode('utf-8-sig').replace('\r\n', '\n')
            self.assertEqual(dumps(json.loads(raw)), raw, f.name)


class EditedRowsKeepTheirIds(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='studio-ids-'))
        rows = [['alpha', '0', '1'], ['beta', '1', '2'], ['gamma', '2', '3']]
        (self.root / 'source' / 'tables').mkdir(parents=True)
        (self.root / 'source' / 'tables' / 'levels.json').write_text(
            dumps(_table('levels', ['global/excel/levels.txt'], ['Name', 'Id', 'Value'], rows)), encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def ids(self):
        return [r['sourceId'] for r in json.loads((self.root / 'source/tables/levels.json').read_text(encoding='utf-8'))['records']]

    def write(self, rows):
        p = StudioProject(self.root)
        p.write_table('global/excel/levels.txt', ['Name', 'Id', 'Value'], rows)
        p.flush()

    def test_an_edited_row_keeps_its_id(self):
        before = self.ids()
        self.write([['alpha', '0', '1'], ['beta', '1', '20'], ['gamma', '2', '30']])
        self.assertEqual(self.ids(), before)

    def test_an_inserted_row_gets_a_new_id_and_edits_around_it_keep_theirs(self):
        before = self.ids()
        self.write([['alpha', '0', '10'], ['new', '9', '9'], ['beta', '1', '2'], ['gamma', '2', '30']])
        after = self.ids()
        self.assertEqual([after[0], after[2], after[3]], before)
        self.assertNotIn(after[1], before)

    def test_a_removed_row_takes_its_id_with_it(self):
        before = self.ids()
        self.write([['alpha', '0', '1'], ['gamma', '2', '3']])
        self.assertEqual(self.ids(), [before[0], before[2]])


if __name__ == '__main__':
    unittest.main()
