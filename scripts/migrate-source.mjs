import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { assert, readTsv, columnDefinitions, recordFromCells, encodeTable, sha256, writeJson, locales } from './lib/source.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'source');
assert(!fs.existsSync(source), 'source/ already exists. Migration is one-time and will not overwrite authored records.');
const slug = value => String(value).normalize('NFKD').replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 65).replace(/-$/, '').toLowerCase() || 'separator';
const targets = ['global/excel/uniqueitems.txt', 'global/excel/base/uniqueitems.txt'];
const originals = targets.map(target => fs.readFileSync(path.join(root, 'data', target)));
assert(originals[0].equals(originals[1]), 'The unique-item banks differ. Model the differences explicitly before migrating.');
const parsed = readTsv(originals[0]);
const schema = {
    schemaVersion: 1, name: 'uniqueitems', targets,
    identityColumns: ['*ID'], columns: columnDefinitions(parsed.headers),
    bom: parsed.bom, newline: parsed.newline, finalNewline: parsed.finalNewline,
};
const records = parsed.rows.map((cells, order) => recordFromCells(cells, order, schema.columns));
schema.protectedRows = records.length;
schema.identitySha256 = sha256(JSON.stringify(records.map(record => [record.sourceId, ...schema.identityColumns.map(key => record.fields[key] ?? '')])));
schema.legacyDuplicateIdentities = {};
for (const field of schema.identityColumns) {
    const values = new Map();
    for (const record of records) {
        const value = record.fields[field];
        if (value !== undefined && value !== '') values.set(value, [...(values.get(value) ?? []), record.sourceId]);
    }
    schema.legacyDuplicateIdentities[field] = Object.fromEntries([...values].filter(([, ids]) => ids.length > 1));
}
assert(encodeTable({ schema, records }).equals(originals[0]), 'Table round-trip mismatch.');
const originalFiles = targets.map((target, index) => ({ path: `data/${target}`, sha256: sha256(originals[index]) }));

// Validate every input before writing the new source tree.
const categories = fs.readdirSync(path.join(root, 'data/local/lng/strings')).filter(name => name.endsWith('.json')).sort().map(name => {
    const relative = `data/local/lng/strings/${name}`;
    const buffer = fs.readFileSync(path.join(root, relative));
    const text = buffer.toString('utf8');
    assert(Buffer.from(text).equals(buffer), `${relative}: invalid UTF-8.`);
    const rows = JSON.parse(text.replace(/^\uFEFF/, ''));
    const keys = Object.keys(rows[0]);
    assert(keys.join('|') === ['id', 'Key', ...locales].join('|'), `${relative}: unexpected string fields/order.`);
    const ids = new Set();
    for (const row of rows) {
        assert(Object.keys(row).sort().join('|') === [...keys].sort().join('|'), `${relative}: inconsistent fields.`);
        assert(!ids.has(row.id), `${relative}: duplicate ID ${row.id}.`);
        ids.add(row.id);
    }
    originalFiles.push({ path: relative, sha256: sha256(buffer), semanticSha256: sha256(JSON.stringify(rows.map(row => Object.fromEntries(keys.map(key => [key, row[key]]))))) });
    return { category: name.slice(0, -5), rows, schema: {
        schemaVersion: 1, category: name.slice(0, -5), target: `local/lng/strings/${name}`, locales,
        bom: text.startsWith('\uFEFF'), newline: text.includes('\r\n') ? '\r\n' : '\n',
        finalNewline: /\r?\n$/.test(text), indent: 4,
    } };
});

writeJson(path.join(source, 'tables/uniqueitems/schema.json'), schema);
for (const record of records) {
    writeJson(path.join(source, `tables/uniqueitems/records/${record.sourceId}-${slug(record.fields.index)}.json`), record);
}
for (const { category, rows, schema } of categories) {
    writeJson(path.join(source, `strings/${category}/schema.json`), schema);
    rows.forEach((row, order) => {
        const { id, Key, ...translations } = row;
        writeJson(path.join(source, `strings/${category}/records/string-${String(id).padStart(5, '0')}-${slug(Key)}.json`), { order, id, Key, translations });
    });
}
writeJson(path.join(source, 'migration.json'), {
    schemaVersion: 1,
    sourceCommit: execFileSync('git', ['-c', `safe.directory=${root.replaceAll('\\', '/')}`, 'rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    note: 'Original checkout byte hashes, including its line endings. JSON semantic hashes preserve record order, IDs, keys and all locale values. Audit baseline only; these hashes are not release gates after intentional content edits.',
    originalFiles,
});
console.log(`Imported ${records.length} unique-item rows and ${categories.reduce((count, category) => count + category.rows.length, 0)} strings. Original data files are still present. Verify the build with --verify-migration before removing only the migrated originals.`);
