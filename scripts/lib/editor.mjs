import fs from 'node:fs';
import path from 'node:path';
import { assert, inside, loadTable, readJson, writeJson, encodeTable, readTsv, cellsFromRecord, clone } from './source.mjs';

export function exportTable(root, tableName, relative) {
    const table = loadTable(inside(root, `source/tables/${tableName}`));
    assert(relative.startsWith('build/edit/') && relative.endsWith('.txt'), 'Editor exports must be build/edit/<name>.txt.');
    const target = inside(root, relative);
    assert(!fs.existsSync(target) && !fs.existsSync(target + '.source.json'), 'Export already exists; choose another filename to preserve unfinished edits.');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, encodeTable(table));
    writeJson(target + '.source.json', {
        schemaVersion: 1, table: tableName, columns: table.schema.columns,
        records: table.records.map(record => ({ sourceId: record.sourceId, order: record.order, columnCount: record.columnCount, fields: record.fields })),
    });
    return target;
}

export function importTable(root, relative) {
    assert(relative.startsWith('build/edit/') && relative.endsWith('.txt'), 'Editor imports must be build/edit/<name>.txt with their .source.json snapshot.');
    const target = inside(root, relative);
    const snapshot = readJson(target + '.source.json');
    assert(snapshot.schemaVersion === 1, 'Unsupported editor snapshot.');
    const table = loadTable(inside(root, `source/tables/${snapshot.table}`));
    const edited = readTsv(fs.readFileSync(target));
    assert(JSON.stringify(snapshot.columns) === JSON.stringify(table.schema.columns), 'Table schema changed since export. Re-export before importing.');
    assert(JSON.stringify(edited.headers) === JSON.stringify(table.schema.columns.map(column => column.header)), 'Edited column headers/order changed.');
    assert(edited.rows.length === snapshot.records.length && table.records.length === snapshot.records.length, 'Row count changed. Re-export; add new rows directly in JSON with explicit slots.');
    const changes = [];
    const conflicts = [];
    const writes = [];
    for (let index = 0; index < snapshot.records.length; index++) {
        const original = snapshot.records[index];
        const current = table.records[index];
        assert(original.sourceId === current.sourceId && original.order === current.order, 'Row identities changed since export.');
        cellsFromRecord(original, table.schema);
        const editedCells = edited.rows[index];
        assert(editedCells.length <= table.schema.columns.length, `Row ${index}: extra columns.`);
        const updated = clone(current);
        for (const [columnIndex, column] of table.schema.columns.entries()) {
            const before = original.fields[column.key] ?? '';
            const desired = editedCells[columnIndex] ?? '';
            const now = current.fields[column.key] ?? '';
            if (before === desired) continue;
            assert(!(table.schema.identityColumns ?? []).includes(column.key), `Cannot change ${column.key} for ${current.sourceId}; editor rows may have been reordered.`);
            if (now !== before && now !== desired) {
                conflicts.push(`${current.sourceId}/${column.key}: exported ${JSON.stringify(before)}, current ${JSON.stringify(now)}, edited ${JSON.stringify(desired)}`);
                continue;
            }
            if (now === desired) continue;
            if (desired === '') delete updated.fields[column.key];
            else updated.fields[column.key] = desired;
            if (desired !== '') updated.columnCount = Math.max(updated.columnCount, columnIndex + 1);
            changes.push({ record: current.sourceId, column: column.key, from: now, to: desired });
        }
        delete updated.file;
        cellsFromRecord(updated, table.schema);
        // Rewrite fields in schema order so spreadsheet imports do not reorder diffs.
        updated.fields = Object.fromEntries(table.schema.columns.flatMap(column => Object.hasOwn(updated.fields, column.key) ? [[column.key, updated.fields[column.key]]] : []));
        if (JSON.stringify(updated.fields) !== JSON.stringify(current.fields) || updated.columnCount !== current.columnCount) writes.push({ file: current.file, record: updated });
    }
    assert(conflicts.length === 0, `Import conflicts; no source files were changed:\n${conflicts.join('\n')}`);
    for (const write of writes) writeJson(write.file, write.record);
    return changes;
}
