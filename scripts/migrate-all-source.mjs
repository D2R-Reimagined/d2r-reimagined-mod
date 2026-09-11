import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';
import { assert, inside, files, posix, readJson, writeJson, readTsv, columnDefinitions, recordFromCells,
    encodeTable, loadTables, loadStrings, loadTextAssets, encodeTextAsset, sha256 } from './lib/source.mjs';
import { encodeStrings } from './lib/build.mjs';

// Preview by default. Validate the complete proposed source in isolation before replacing anything.
export function migrateAllSource(root, { write = false } = {}) {
    const sourceSnapshot = new Map(files(inside(root, 'source')).map(file => [file, sha256(fs.readFileSync(file))]));
    const tables = loadTables(root);
    const stringCategories = ['standard', 'full'].map(mode => loadStrings(root, mode));
    const stringsBefore = stringCategories.map(categories => categories.map(encodeStrings));
    const outputs = new Map(tables.flatMap(table => table.schema.targets.map(target => [target, encodeTable(table)])));
    for (const asset of loadTextAssets(root)) {
        assert(!outputs.has(asset.target), `Duplicate existing output: ${asset.target}`);
        outputs.set(asset.target, asset.content);
    }
    const pending = new Map();
    const removals = new Map();
    const recordDirectories = new Set();
    const originalFiles = new Map(readJson(inside(root, 'source/migration.json')).originalFiles.map(entry => [entry.path, entry]));
    function schedule(relative, value) {
        assert(!pending.has(relative), `Duplicate migration destination: ${relative}`);
        inside(root, relative);
        pending.set(relative, value);
    }
    function removeLater(file) {
        removals.set(file, sha256(fs.readFileSync(file)));
    }
    function baseline(relative, bytes) {
        const previous = originalFiles.get(relative);
        assert(!previous || previous.sha256 === sha256(bytes), `Original migration baseline differs: ${relative}`);
        originalFiles.set(relative, { path: relative, sha256: sha256(bytes) });
    }
    for (const category of stringCategories[1]) {
        const file = inside(root, `data/${category.schema.target}`);
        if (!fs.existsSync(file)) continue;
        assert(isDeepStrictEqual(readJson(file), category.rows), `Runtime string JSON differs from source: ${category.schema.target}`);
        removeLater(file);
    }
    for (const table of tables) {
        schedule(`source/tables/${table.schema.name}/schema.json`, table.schema);
        schedule(`source/tables/${table.schema.name}/records.json`, table.records.map(({ file, ...record }) => record));
        if (!table.recordsFile) {
            table.records.forEach(record => removeLater(record.file));
            recordDirectories.add(inside(root, `source/tables/${table.schema.name}/records`));
        }
    }
    for (const category of fs.readdirSync(inside(root, 'source/strings')).sort()) {
        const location = inside(root, `source/strings/${category}`);
        const combined = inside(location, 'records.json');
        const oldFiles = fs.existsSync(combined) ? [] : files(inside(location, 'records'));
        const records = fs.existsSync(combined) ? readJson(combined) : oldFiles.map(readJson).sort((a, b) => a.order - b.order);
        schedule(`source/strings/${category}/schema.json`, readJson(inside(location, 'schema.json')));
        schedule(`source/strings/${category}/records.json`, records);
        if (!fs.existsSync(combined)) {
            oldFiles.forEach(removeLater);
            recordDirectories.add(inside(location, 'records'));
        }
    }
    const newTables = new Map();
    const txtFiles = files(inside(root, 'data')).filter(file => file.toLowerCase().endsWith('.txt'));
    for (const file of txtFiles) {
        const relative = posix(path.relative(inside(root, 'data'), file));
        const bytes = fs.readFileSync(file);
        if (outputs.has(relative)) {
            assert(outputs.get(relative).equals(bytes), `TXT differs from existing JSON source: ${relative}`);
        } else if (relative === 'global/dataversionbuild.txt') {
            const asset = { schemaVersion: 1, target: relative, content: bytes.toString('utf8') };
            assert(encodeTextAsset(asset).equals(bytes), `Text round-trip mismatch: ${relative}`);
            schedule('source/text/dataversionbuild.json', asset);
        } else {
            assert(/^global\/excel\/(?:base\/)?[a-z0-9]+\.txt$/.test(relative), `Unrecognized TXT asset: ${relative}`);
            const basename = path.basename(relative, '.txt');
            // Share banks only when every byte matches, including headers and line endings.
            const group = `${basename}:${sha256(bytes)}`;
            let table = newTables.get(group);
            if (!table) {
                const name = relative.includes('/base/') ? `${basename}-base` : basename;
                const parsed = readTsv(bytes);
                const schema = {
                    schemaVersion: 1, name, targets: [], identityColumns: [],
                    identityPolicy: 'Physical row slots are preserved. Table-specific runtime identity and reference rules are not yet defined.',
                    columns: columnDefinitions(parsed.headers), bom: parsed.bom, newline: parsed.newline, finalNewline: parsed.finalNewline,
                };
                const records = parsed.rows.map((cells, order) => recordFromCells(cells, order, schema.columns));
                schema.protectedRows = records.length;
                schema.identitySha256 = sha256(JSON.stringify(records.map(record => [record.sourceId])));
                table = { schema, records };
                newTables.set(group, table);
            }
            // Main comes after base in filesystem order; prefer the unsuffixed name for shared banks.
            if (!relative.includes('/base/')) table.schema.name = basename;
            table.schema.targets.push(relative);
            assert(encodeTable(table).equals(bytes), `Table round-trip mismatch: ${relative}`);
        }
        baseline(`data/${relative}`, bytes);
        removeLater(file);
    }
    for (const table of newTables.values()) {
        table.schema.targets.sort((a, b) => a.includes('/base/') - b.includes('/base/') || a.localeCompare(b));
        schedule(`source/tables/${table.schema.name}/schema.json`, table.schema);
        schedule(`source/tables/${table.schema.name}/records.json`, table.records);
    }
    for (const file of files(path.join(root, 'source/text'))) {
        const relative = posix(path.relative(root, file));
        if (!pending.has(relative)) schedule(relative, readJson(file));
    }
    const migration = readJson(inside(root, 'source/migration.json'));
    schedule('source/migration.json', { ...migration, originalFiles: [...originalFiles.values()] });
    const build = inside(root, 'build');
    fs.mkdirSync(build, { recursive: true });
    const staging = fs.mkdtempSync(path.join(build, '.source-migration-'));
    try {
        for (const [relative, value] of pending) writeJson(inside(staging, relative), value);
        const stagedTables = loadTables(staging);
        const stagedOutputs = new Map(stagedTables.flatMap(table => table.schema.targets.map(target => [target, encodeTable(table)])));
        for (const asset of loadTextAssets(staging)) {
            assert(!stagedOutputs.has(asset.target), `Duplicate staged output: ${asset.target}`);
            stagedOutputs.set(asset.target, asset.content);
        }
        for (const [target, before] of outputs) assert(stagedOutputs.get(target)?.equals(before), `Changed existing table: ${target}`);
        for (const file of txtFiles) {
            const relative = posix(path.relative(inside(root, 'data'), file));
            assert(stagedOutputs.get(relative)?.equals(fs.readFileSync(file)), `Changed TXT: ${relative}`);
        }
        for (const [index, mode] of ['standard', 'full'].entries()) {
            const after = loadStrings(staging, mode).map(encodeStrings);
            assert(after.length === stringsBefore[index].length && after.every((buffer, i) => buffer.equals(stringsBefore[index][i])), `Changed ${mode} strings.`);
        }
        const report = { write, tables: stagedTables.length, newTables: newTables.size, catalogs: stringsBefore[0].length, txtFiles: txtFiles.length, removedRecordFiles: [...removals.keys()].filter(file => file.includes(`${path.sep}records${path.sep}`)).length };
        if (write) {
            const currentSources = files(inside(root, 'source'));
            assert(currentSources.length === sourceSnapshot.size && currentSources.every(file => sourceSnapshot.get(file) === sha256(fs.readFileSync(file))), 'JSON source changed during migration; retry with a fresh snapshot.');
            for (const [file, hash] of removals) assert(sha256(fs.readFileSync(file)) === hash, `Source changed during migration: ${file}`);
            for (const [relative] of pending) {
                const destination = inside(root, relative);
                const bytes = fs.readFileSync(inside(staging, relative));
                if (fs.existsSync(destination) && fs.readFileSync(destination).equals(bytes)) continue;
                fs.mkdirSync(path.dirname(destination), { recursive: true });
                fs.writeFileSync(destination, bytes);
                assert(fs.readFileSync(destination).equals(bytes), `Source write mismatch: ${relative}`);
            }
            for (const file of removals.keys()) fs.unlinkSync(file);
            for (const directory of recordDirectories) fs.rmdirSync(directory);
        }
        return report;
    } finally {
        // staging is created under this workspace's checked build directory.
        assert(path.resolve(staging).startsWith(path.resolve(build) + path.sep), 'Staging escaped build directory.');
        fs.rmSync(staging, { recursive: true, force: true });
    }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    try {
        assert(process.argv.slice(2).every(arg => arg === '--write'), 'Usage: node scripts/migrate-all-source.mjs [--write]');
        console.log(JSON.stringify(migrateAllSource(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), { write: process.argv.includes('--write') }), null, 4));
    } catch (error) {
        console.error(error.message);
        process.exitCode = 1;
    }
}
