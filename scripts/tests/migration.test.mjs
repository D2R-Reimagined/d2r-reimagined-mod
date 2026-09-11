import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { migrateAllSource } from '../migrate-all-source.mjs';
import { loadTables, loadStrings, loadTextAssets, encodeTable, writeJson, locales, sha256, replaceJson } from '../lib/source.mjs';
import { buildProfile } from '../lib/build.mjs';
import { reviewString } from '../lib/editor.mjs';

function fixture(t) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'reimagined-migration-test-'));
    t.after(() => fs.rmSync(root, { recursive: true, force: true }));
    fs.mkdirSync(path.join(root, 'source/tables'), { recursive: true });
    writeJson(path.join(root, 'source/migration.json'), { schemaVersion: 1, originalFiles: [] });
    writeJson(path.join(root, 'source/strings/items/schema.json'), { schemaVersion: 1, category: 'items', target: 'local/lng/strings/item-names.json', locales, indent: 4, newline: '\n', finalNewline: true });
    for (let index = 0; index < 2; index++) writeJson(path.join(root, `source/strings/items/records/string-${50000 + index}-example.json`), {
        order: index, id: 50000 + index, Key: `Example${index}`, translations: Object.fromEntries(locales.map(locale => [locale, 'Long %d 魔法'])),
    });
    for (const id of ['standard', 'd2rl']) writeJson(path.join(root, `compatibility/${id}/profile.json`), { schemaVersion: 1, id, stringMode: id === 'standard' ? 'standard' : 'full', tableOverrides: [], assetOverrides: [] });
    writeJson(path.join(root, 'modinfo.json'), { version: 'test' });
    fs.mkdirSync(path.join(root, 'data/global/excel/base'), { recursive: true });
    return root;
}

test('full migration shares identical banks, separates differing banks and preserves every byte', t => {
    const root = fixture(t);
    const originals = {
        'global/excel/example.txt': '\uFEFFname\t\tname\r\nExample\t0\t\r\n\r\nExpansion\r\n',
        'global/excel/base/example.txt': '\uFEFFname\t\tname\r\nExample\t0\t\r\n\r\nExpansion\r\n',
        'global/excel/different.txt': 'name\tvalue\nMain\t1',
        'global/excel/base/different.txt': 'name\tvalue\nBase\t2',
        'global/dataversionbuild.txt': '93847',
    };
    for (const [relative, bytes] of Object.entries(originals)) fs.writeFileSync(path.join(root, 'data', relative), bytes);
    assert.equal(migrateAllSource(root).tables, 3);
    assert(fs.existsSync(path.join(root, 'data/global/excel/example.txt')));
    assert(!fs.existsSync(path.join(root, 'source/tables/example')));
    const report = migrateAllSource(root, { write: true });
    assert.equal(report.catalogs, 1);
    assert.equal(report.txtFiles, 5);
    assert.equal(report.removedRecordFiles, 2);
    const tables = loadTables(root);
    assert.equal(tables.find(table => table.schema.name === 'example').schema.targets.length, 2);
    assert.deepEqual(tables.map(table => table.schema.name), ['different', 'different-base', 'example']);
    for (const table of tables) for (const target of table.schema.targets) assert.deepEqual(encodeTable(table), Buffer.from(originals[target]));
    assert.deepEqual(loadTextAssets(root)[0].content, Buffer.from('93847'));
    assert.equal(loadStrings(root, 'standard')[0].rows.length, 2);
    for (const relative of Object.keys(originals)) assert(!fs.existsSync(path.join(root, 'data', relative)));
    assert.equal(migrateAllSource(root, { write: true }).newTables, 0);
    for (const profile of ['standard', 'd2rl']) {
        const manifest = buildProfile(root, profile, { verifyMigration: true });
        assert(manifest.migrationVerification.every(entry => entry.byteIdentical));
        for (const [relative, bytes] of Object.entries(originals)) assert.deepEqual(fs.readFileSync(path.join(root, `build/${profile}/mods/Reimagined/Reimagined.mpq/data/${relative}`)), Buffer.from(bytes));
    }
});

test('lossy or unsupported input fails before authored sources are changed', t => {
    const root = fixture(t);
    const file = path.join(root, 'data/global/excel/bad.txt');
    fs.writeFileSync(file, Buffer.from([0xff]));
    assert.throws(() => migrateAllSource(root, { write: true }), /lossy/);
    assert.deepEqual(fs.readFileSync(file), Buffer.from([0xff]));
    assert(!fs.existsSync(path.join(root, 'source/strings/items/records.json')));
    fs.writeFileSync(file, 'a\r\nb\nc');
    assert.throws(() => migrateAllSource(root, { write: true }), /Mixed/);
    assert(fs.existsSync(path.join(root, 'source/strings/items/records/string-50000-example.json')));
});

test('recreated TXT with competing changes is not discarded', t => {
    const root = fixture(t);
    const file = path.join(root, 'data/global/excel/example.txt');
    fs.writeFileSync(file, 'name\nOriginal');
    migrateAllSource(root, { write: true });
    const source = path.join(root, 'source/tables/example/records.json');
    const before = fs.readFileSync(source);
    fs.writeFileSync(file, 'name\nChanged');
    assert.throws(() => migrateAllSource(root, { write: true }), /differs from existing/);
    assert.deepEqual(fs.readFileSync(source), before);
    assert.equal(fs.readFileSync(file, 'utf8'), 'name\nChanged');
});

test('recreated runtime catalogs and version TXT cannot overwrite authored edits', t => {
    const root = fixture(t);
    fs.writeFileSync(path.join(root, 'data/global/dataversionbuild.txt'), '93847');
    migrateAllSource(root, { write: true });
    const runtime = path.join(root, 'data/local/lng/strings/item-names.json');
    const rows = loadStrings(root, 'full')[0].rows;
    writeJson(runtime, rows);
    migrateAllSource(root, { write: true });
    assert(!fs.existsSync(runtime));
    rows[0].enUS = 'Competing edit';
    writeJson(runtime, rows);
    assert.throws(() => migrateAllSource(root, { write: true }), /Runtime string JSON differs/);
    assert.equal(JSON.parse(fs.readFileSync(runtime))[0].enUS, 'Competing edit');
    fs.unlinkSync(runtime);
    const source = path.join(root, 'source/text/dataversionbuild.json');
    writeJson(source, { schemaVersion: 1, target: 'global/dataversionbuild.txt', content: '93848' });
    fs.writeFileSync(path.join(root, 'data/global/dataversionbuild.txt'), '93847');
    assert.throws(() => migrateAllSource(root, { write: true }), /differs from existing/);
    assert.equal(JSON.parse(fs.readFileSync(source)).content, '93848');
});

test('catalog review targets one ID, retains other records and rejects invalid changes without writes', t => {
    const root = fixture(t);
    migrateAllSource(root, { write: true });
    const relative = 'source/strings/items/records.json';
    const file = path.join(root, relative);
    const records = JSON.parse(fs.readFileSync(file));
    records[0].standardTranslations = { enUS: 'Short %d' };
    writeJson(file, records);
    assert.throws(() => loadStrings(root, 'standard'), /needs review/);
    assert.equal(reviewString(root, relative, 50000).key, 'Example0');
    const reviewed = JSON.parse(fs.readFileSync(file));
    assert.equal(reviewed[0].standardReviewedAgainst.enUS, sha256(records[0].translations.enUS));
    assert.deepEqual(reviewed[1], records[1]);
    assert.equal(loadStrings(root, 'standard')[0].rows[0].enUS, 'Short %d');
    assert.equal(loadStrings(root, 'full')[0].rows[0].enUS, 'Long %d 魔法');
    reviewed[0].standardTranslations.enUS = 'Wrong %s';
    writeJson(file, reviewed);
    const before = fs.readFileSync(file);
    assert.throws(() => reviewString(root, relative, 50000), /placeholders/);
    assert.throws(() => reviewString(root, relative, 42), /exactly one/);
    assert.deepEqual(fs.readFileSync(file), before);
});

test('catalog duplicate sources, IDs, keys and row orders remain errors', t => {
    const root = fixture(t);
    migrateAllSource(root, { write: true });
    const directory = path.join(root, 'source/strings/items');
    const file = path.join(directory, 'records.json');
    const records = JSON.parse(fs.readFileSync(file));
    fs.mkdirSync(path.join(directory, 'records'));
    assert.throws(() => loadStrings(root, 'standard'), /two record sources/);
    fs.rmdirSync(path.join(directory, 'records'));
    for (const [field, pattern] of [['id', /duplicate numeric/], ['Key', /duplicate key/], ['order', /duplicate string order/]]) {
        const copy = structuredClone(records);
        copy[1][field] = copy[0][field];
        writeJson(file, copy);
        assert.throws(() => loadStrings(root, 'standard'), pattern);
    }
    writeJson(file, {});
    assert.throws(() => loadStrings(root, 'standard'), /expected an array/);
});

test('interrupted replacement cannot overwrite source or an existing temporary file', t => {
    const root = fixture(t);
    const file = path.join(root, 'source/migration.json');
    const before = fs.readFileSync(file);
    fs.writeFileSync(file + '.tmp', 'unfinished');
    assert.throws(() => replaceJson(file, {}), /EEXIST/);
    assert.deepEqual(fs.readFileSync(file), before);
    assert.equal(fs.readFileSync(file + '.tmp', 'utf8'), 'unfinished');
});
