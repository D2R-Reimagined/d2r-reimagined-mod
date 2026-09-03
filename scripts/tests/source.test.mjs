import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { readTsv, columnDefinitions, recordFromCells, encodeTable, cellsFromRecord, loadTable, applyTableOverrides, resolveString, stringReport, sha256, inside, writeJson, locales } from '../lib/source.mjs';
import { buildProfile } from '../lib/build.mjs';
import { exportTable, importTable } from '../lib/editor.mjs';

function tableFrom(text) {
    const parsed = readTsv(Buffer.from(text));
    const schema = { schemaVersion: 1, name: 'uniqueitems', targets: ['global/excel/uniqueitems.txt', 'global/excel/base/uniqueitems.txt'], identityColumns: ['*ID'], columns: columnDefinitions(parsed.headers), bom: parsed.bom, newline: parsed.newline, finalNewline: parsed.finalNewline };
    return { schema, records: parsed.rows.map((cells, index) => recordFromCells(cells, index, schema.columns)) };
}

const text = '\uFEFFindex\t*ID\tmin1\tmax1\t*eol\r\nExample\t0\t\t160\t0\r\n\r\nExpansion\r\n';
const makeString = () => ({ order: 0, id: 50000, Key: 'Example', translations: Object.fromEntries(locales.map(locale => [locale, 'Long description %d ÿc1魔法'])) });
function fixture(t) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'reimagined-source-test-'));
    t.after(() => fs.rmSync(root, { recursive: true, force: true }));
    const table = tableFrom(text);
    writeJson(path.join(root, 'source/tables/uniqueitems/schema.json'), table.schema);
    table.records.forEach(record => writeJson(path.join(root, `source/tables/uniqueitems/records/${record.sourceId}-example.json`), record));
    writeJson(path.join(root, 'source/strings/items/schema.json'), { schemaVersion: 1, category: 'items', target: 'local/lng/strings/item-names.json', locales, indent: 4, newline: '\n', bom: false, finalNewline: true });
    writeJson(path.join(root, 'source/strings/items/records/string-50000-example.json'), makeString());
    for (const id of ['standard', 'd2rl']) writeJson(path.join(root, `compatibility/${id}/profile.json`), { schemaVersion: 1, id, stringMode: id === 'standard' ? 'standard' : 'full', tableOverrides: [], assetOverrides: [] });
    fs.mkdirSync(path.join(root, 'data/hd'), { recursive: true });
    fs.writeFileSync(path.join(root, 'data/hd/example.bin'), Buffer.from([0, 255, 1, 0]));
    writeJson(path.join(root, 'modinfo.json'), { name: 'Reimagined', version: 'test', savepath: 'ReimaginedThree/' });
    return root;
}

test('TSV preserves BOM, CRLF, blank versus zero, separators, short rows and trailing cells', () => {
    const table = tableFrom(text);
    assert.deepEqual(encodeTable(table), Buffer.from(text));
    assert.equal(table.records[0].fields.min1, undefined);
    assert.equal(table.records[0].fields['*ID'], '0');
    assert.equal(table.records[1].columnCount, 1);
});

test('duplicate and blank headers keep distinct column identities', () => {
    const value = 'name\t\tname\tname#3\na\tb\tc\td';
    const table = tableFrom(value);
    assert.equal(new Set(table.schema.columns.map(column => column.key)).size, 4);
    assert.deepEqual(encodeTable(table), Buffer.from(value));
});

test('rejects lossy UTF-8, mixed newlines, unknown columns and invalid TSV cells', () => {
    assert.throws(() => readTsv(Buffer.from([0xff])), /lossy/);
    assert.throws(() => readTsv(Buffer.from('a\r\nb\nc')), /Mixed/);
    const table = tableFrom(text);
    table.records[0].fields.typo = '1';
    assert.throws(() => cellsFromRecord(table.records[0], table.schema), /unknown/);
    delete table.records[0].fields.typo;
    table.records[0].fields.min1 = '1\t2';
    assert.throws(() => encodeTable(table), /without tabs/);
});

test('override affects only its declared bank and preserves identity', () => {
    const table = tableFrom(text);
    const rule = { table: 'uniqueitems', record: 'row-00000', targets: [table.schema.targets[0]], reason: 'Fixture', rulePath: 'fixture.json', changes: { max1: { expect: '160', value: '180' } } };
    const result = applyTableOverrides(table, [rule], table.schema.targets[0]);
    assert.equal(result.table.records[0].fields.max1, '180');
    assert.equal(table.records[0].fields.max1, '160');
    assert.equal(applyTableOverrides(table, [rule], table.schema.targets[1]).changes.length, 0);
    rule.changes = { '*ID': { expect: '0', value: '1' } };
    assert.throws(() => applyTableOverrides(table, [rule], table.schema.targets[0]), /identity/);
});

test('stale, duplicate and unknown overrides fail instead of silently winning', () => {
    const table = tableFrom(text);
    const rule = { table: 'uniqueitems', record: 'row-00000', reason: 'Fixture', rulePath: 'fixture.json', changes: { max1: { expect: '160', value: '180' } } };
    assert.throws(() => applyTableOverrides(table, [rule, rule], table.schema.targets[0]), /Conflicting/);
    rule.changes.max1.expect = '150';
    assert.throws(() => applyTableOverrides(table, [rule], table.schema.targets[0]), /Stale/);
    rule.record = 'missing';
    assert.throws(() => applyTableOverrides(table, [rule], table.schema.targets[0]), /Missing override/);
});

test('compact translations require review, preserve placeholders and inherit other locales', () => {
    const record = makeString();
    record.standardTranslations = { enUS: 'Short %d ÿc1魔法' };
    assert.throws(() => resolveString(record, 'standard', locales, 'fixture'), /needs review/);
    record.standardReviewedAgainst = { enUS: sha256(record.translations.enUS) };
    const standard = resolveString(record, 'standard', locales, 'fixture');
    assert.equal(standard.output.enUS, record.standardTranslations.enUS);
    assert.equal(standard.output.frFR, record.translations.frFR);
    assert.equal(resolveString(record, 'full', locales, 'fixture').output.enUS, record.translations.enUS);
    record.standardTranslations.enUS = 'Short %s';
    assert.throws(() => resolveString(record, 'standard', locales, 'fixture'), /placeholders/);
    record.translations.enUS += ' changed';
    assert.throws(() => resolveString(record, 'standard', locales, 'fixture'), /needs review/);
});

test('budget measures Unicode and terminators without claiming runtime headroom', () => {
    const record = makeString();
    const row = resolveString(record, 'full', locales, 'fixture').output;
    const report = stringReport([{ schema: { target: 'fixture.json' }, rows: [row] }]);
    assert.equal(report.totals.keyUtf8BytesWithNull, 8);
    assert.equal(report.byLocale.enUS.utf8BytesWithNull, Buffer.byteLength(row.enUS) + 1);
    assert.equal(report.byLocale.enUS.utf16leBytesWithNull, Buffer.byteLength(row.enUS, 'utf16le') + 2);
    assert.equal(report.runtimeRemaining, null);
});

test('source row deletion/reordering cannot compact runtime IDs', t => {
    const root = fixture(t);
    fs.unlinkSync(path.join(root, 'source/tables/uniqueitems/records/row-00001-example.json'));
    assert.throws(() => loadTable(path.join(root, 'source/tables/uniqueitems')), /missing or duplicate/);
});

test('build emits both banks and full assets, and repeat builds are deterministic', t => {
    const root = fixture(t);
    const first = buildProfile(root, 'standard');
    const second = buildProfile(root, 'standard');
    const d2rl = buildProfile(root, 'd2rl');
    assert.deepEqual(first, second);
    assert.deepEqual(first.files, d2rl.files);
    for (const target of ['global/excel/uniqueitems.txt', 'global/excel/base/uniqueitems.txt']) assert.deepEqual(fs.readFileSync(path.join(root, `build/standard/mods/Reimagined/Reimagined.mpq/data/${target}`)), Buffer.from(text));
    assert.deepEqual(fs.readFileSync(path.join(root, 'build/standard/mods/Reimagined/Reimagined.mpq/data/hd/example.bin')), Buffer.from([0, 255, 1, 0]));
});

test('build rejects duplicate editable sources and protects last valid output on error', t => {
    const root = fixture(t);
    const first = buildProfile(root, 'standard');
    fs.mkdirSync(path.join(root, 'data/global/excel'), { recursive: true });
    fs.writeFileSync(path.join(root, 'data/global/excel/uniqueitems.txt'), text);
    assert.throws(() => buildProfile(root, 'standard'), /Two editable sources/);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(root, 'build/standard/build-manifest.json'))), first);
});

test('paths and unknown output folders are protected', t => {
    const root = fixture(t);
    for (const invalid of ['../outside', '/absolute', 'C:/outside', 'foo\\..\\bar', 'foo//bar']) assert.throws(() => inside(root, invalid), /Unsafe/);
    fs.mkdirSync(path.join(root, 'build/standard'), { recursive: true });
    fs.writeFileSync(path.join(root, 'build/standard/keep.txt'), 'keep');
    assert.throws(() => buildProfile(root, 'standard'), /build-manifest/);
    assert.equal(fs.readFileSync(path.join(root, 'build/standard/keep.txt'), 'utf8'), 'keep');
});

test('asset overrides check old hashes and cannot bypass generated table rules', t => {
    const root = fixture(t);
    const profilePath = path.join(root, 'compatibility/d2rl/profile.json');
    const profile = JSON.parse(fs.readFileSync(profilePath));
    fs.writeFileSync(path.join(root, 'compatibility/d2rl/replacement.bin'), 'new');
    profile.assetOverrides = [{ source: 'replacement.bin', target: 'hd/example.bin', expectSha256: 'wrong', reason: 'Fixture' }];
    writeJson(profilePath, profile);
    assert.throws(() => buildProfile(root, 'd2rl'), /Stale asset/);
    profile.assetOverrides[0].expectSha256 = sha256(Buffer.from([0, 255, 1, 0]));
    writeJson(profilePath, profile);
    assert.equal(buildProfile(root, 'd2rl').changes.length, 1);
    profile.assetOverrides[0].target = 'global/excel/uniqueitems.txt';
    writeJson(profilePath, profile);
    assert.throws(() => buildProfile(root, 'd2rl'), /cannot replace/);
});

test('spreadsheet import merges edited cells with newer independent source edits', t => {
    const root = fixture(t);
    const exported = exportTable(root, 'uniqueitems', 'build/edit/items.txt');
    const recordPath = path.join(root, 'source/tables/uniqueitems/records/row-00000-example.json');
    const record = JSON.parse(fs.readFileSync(recordPath));
    record.fields.min1 = '25';
    writeJson(recordPath, record);
    fs.writeFileSync(exported, text.replace('\t160\t', '\t180\t'));
    const changes = importTable(root, 'build/edit/items.txt');
    const result = JSON.parse(fs.readFileSync(recordPath));
    assert.equal(changes.length, 1);
    assert.equal(result.fields.max1, '180');
    assert.equal(result.fields.min1, '25');
    assert.equal(importTable(root, 'build/edit/items.txt').length, 0);
});

test('spreadsheet conflicts are detected before any source write', t => {
    const root = fixture(t);
    const exported = exportTable(root, 'uniqueitems', 'build/edit/items.txt');
    const recordPath = path.join(root, 'source/tables/uniqueitems/records/row-00000-example.json');
    const record = JSON.parse(fs.readFileSync(recordPath));
    record.fields.max1 = '175';
    writeJson(recordPath, record);
    fs.writeFileSync(exported, text.replace('Example\t0\t\t160\t', 'Example\t0\t30\t180\t'));
    assert.throws(() => importTable(root, 'build/edit/items.txt'), /Import conflicts/);
    assert.deepEqual(JSON.parse(fs.readFileSync(recordPath)), record);
});

test('spreadsheet reordering and discarded rows are rejected', t => {
    const root = fixture(t);
    const exported = exportTable(root, 'uniqueitems', 'build/edit/items.txt');
    fs.writeFileSync(exported, text.replace('Example\t0', 'Example\t1'));
    assert.throws(() => importTable(root, 'build/edit/items.txt'), /Cannot change/);
    fs.writeFileSync(exported, text.replace('\r\nExpansion', ''));
    assert.throws(() => importTable(root, 'build/edit/items.txt'), /Row count/);
    assert.throws(() => exportTable(root, 'uniqueitems', 'build/edit/items.txt'), /already exists/);
});

test('protected original runtime IDs cannot change or disappear at the end', t => {
    const root = fixture(t);
    const directory = path.join(root, 'source/tables/uniqueitems');
    const table = loadTable(directory);
    table.schema.protectedRows = table.records.length;
    table.schema.identitySha256 = sha256(JSON.stringify(table.records.map(record => [record.sourceId, record.fields['*ID'] ?? ''])));
    writeJson(path.join(directory, 'schema.json'), table.schema);
    const recordPath = path.join(directory, 'records/row-00000-example.json');
    const record = JSON.parse(fs.readFileSync(recordPath));
    record.fields['*ID'] = '5';
    writeJson(recordPath, record);
    assert.throws(() => loadTable(directory), /runtime IDs changed/);
    record.fields['*ID'] = '0';
    writeJson(recordPath, record);
    fs.unlinkSync(path.join(directory, 'records/row-00002-example.json'));
    assert.throws(() => loadTable(directory), /row slots cannot be removed/);
});

test('D2RLoader plugin assets install beside the MPQ and never enter Standard', t => {
    const root = fixture(t);
    const profilePath = path.join(root, 'compatibility/d2rl/profile.json');
    const profile = JSON.parse(fs.readFileSync(profilePath));
    fs.writeFileSync(path.join(root, 'compatibility/d2rl/fixture.dll'), 'fixture only');
    profile.assetOverrides = [{ scope: 'mod', source: 'fixture.dll', target: 'd2rloader/plugins/fixture.dll', expectSha256: null, reason: 'Fixture' }];
    writeJson(profilePath, profile);
    const d2rl = buildProfile(root, 'd2rl');
    const standard = buildProfile(root, 'standard');
    assert(d2rl.files.some(file => file.path === 'mods/Reimagined/d2rloader/plugins/fixture.dll'));
    assert(!standard.files.some(file => file.path.includes('fixture.dll')));
    assert(!fs.existsSync(path.join(root, 'build/standard/mods/Reimagined/d2rloader')));
    profile.assetOverrides[0].target = 'd2rloader/config/private.toml';
    writeJson(profilePath, profile);
    assert.throws(() => buildProfile(root, 'd2rl'), /runtime config/);
});

test('legacy duplicate IDs allow only the exact pre-existing source rows', t => {
    const root = fixture(t);
    const directory = path.join(root, 'source/tables/uniqueitems');
    const rowPath = path.join(directory, 'records/row-00001-example.json');
    const row = JSON.parse(fs.readFileSync(rowPath));
    row.columnCount = 5;
    row.fields['*ID'] = '0';
    writeJson(rowPath, row);
    assert.throws(() => loadTable(directory), /new duplicate identity/);
    const schemaPath = path.join(directory, 'schema.json');
    const schema = JSON.parse(fs.readFileSync(schemaPath));
    schema.legacyDuplicateIdentities = { '*ID': { '0': ['row-00000', 'row-00001'] } };
    writeJson(schemaPath, schema);
    assert.equal(loadTable(directory).records.length, 3);
    const lastPath = path.join(directory, 'records/row-00002-example.json');
    const last = JSON.parse(fs.readFileSync(lastPath));
    last.columnCount = 5;
    last.fields['*ID'] = '0';
    writeJson(lastPath, last);
    assert.throws(() => loadTable(directory), /new duplicate identity/);
});

test('composite table identities are unique as complete tuples', t => {
    const root = fixture(t);
    const directory = path.join(root, 'source/tables/uniqueitems');
    const schemaPath = path.join(directory, 'schema.json');
    const schema = JSON.parse(fs.readFileSync(schemaPath));
    schema.identityColumns = ['index', '*ID'];
    writeJson(schemaPath, schema);
    const secondPath = path.join(directory, 'records/row-00001-example.json');
    const second = JSON.parse(fs.readFileSync(secondPath));
    second.columnCount = 5;
    second.fields.index = 'Example';
    second.fields['*ID'] = '0';
    writeJson(secondPath, second);
    assert.throws(() => loadTable(directory), /new duplicate identity/);
    schema.legacyDuplicateIdentityTuples = { '["Example","0"]': ['row-00000', 'row-00001'] };
    writeJson(schemaPath, schema);
    assert.equal(loadTable(directory).records.length, 3);
    const thirdPath = path.join(directory, 'records/row-00002-example.json');
    const third = JSON.parse(fs.readFileSync(thirdPath));
    third.columnCount = 5;
    third.fields.index = 'Example';
    third.fields['*ID'] = '0';
    writeJson(thirdPath, third);
    assert.throws(() => loadTable(directory), /new duplicate identity/);
});

test('D2RLoader metadata template derives the mod version and remains profile-only', t => {
    const root = fixture(t);
    const profilePath = path.join(root, 'compatibility/d2rl/profile.json');
    const profile = JSON.parse(fs.readFileSync(profilePath));
    fs.mkdirSync(path.join(root, 'compatibility/d2rl/assets'), { recursive: true });
    writeJson(path.join(root, 'compatibility/d2rl/assets/metadata.json'), {
        schemaVersion: 1,
        metadata: { modVersion: '${mod.version}', author: 'Reimagined', description: 'Fixture', website: 'https://example.test' },
        d2rloader: { version: '1.1.0' },
    });
    profile.assetOverrides = [{ scope: 'mod', source: 'assets/metadata.json', target: 'd2rloader/metadata.json', transform: 'json-template', expectSha256: null, reason: 'Fixture' }];
    writeJson(profilePath, profile);
    const d2rl = buildProfile(root, 'd2rl');
    buildProfile(root, 'standard');
    const generated = JSON.parse(fs.readFileSync(path.join(root, 'build/d2rl/mods/Reimagined/d2rloader/metadata.json')));
    assert.equal(generated.metadata.modVersion, 'test');
    assert(d2rl.files.some(file => file.path === 'mods/Reimagined/d2rloader/metadata.json'));
    assert(!fs.existsSync(path.join(root, 'build/standard/mods/Reimagined/d2rloader/metadata.json')));
});
