import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const locales = ['enUS', 'zhTW', 'deDE', 'esES', 'frFR', 'itIT', 'koKR', 'plPL', 'esMX', 'jaJP', 'ptBR', 'ruRU', 'zhCN'];
export const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');
export const clone = value => structuredClone(value);
export const posix = value => value.split(path.sep).join('/');

export function assert(condition, message) {
    if (!condition) throw new Error(message);
}

export function readJson(file) {
    try {
        return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
    } catch (error) {
        throw new Error(`${file}: ${error.message}`);
    }
}

export function writeJson(file, value) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(value, null, 4) + '\n');
}

export function inside(root, relative) {
    if (fs.existsSync(root)) assert(!fs.lstatSync(root).isSymbolicLink(), `Linked root: ${root}`);
    assert(typeof relative === 'string' && relative.length > 0 && !relative.includes('\\')
        && !relative.includes(':') && !relative.startsWith('/')
        && relative.split('/').every(part => part && part !== '.' && part !== '..'), `Unsafe relative path: ${relative}`);
    const resolved = path.resolve(root, relative);
    assert(resolved.startsWith(path.resolve(root) + path.sep), `Path escapes root: ${relative}`);
    let current = path.resolve(root);
    for (const part of relative.split('/')) {
        current = path.join(current, part);
        if (fs.existsSync(current)) assert(!fs.lstatSync(current).isSymbolicLink(), `Linked paths are not supported: ${current}`);
    }
    return resolved;
}

export function files(root) {
    if (!fs.existsSync(root)) return [];
    assert(!fs.lstatSync(root).isSymbolicLink(), `Linked directory: ${root}`);
    return fs.readdirSync(root, { withFileTypes: true }).sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0)
        .flatMap(entry => {
            const file = path.join(root, entry.name);
            assert(!entry.isSymbolicLink(), `Linked file: ${file}`);
            return entry.isDirectory() ? files(file) : [file];
        });
}

export function readTsv(buffer) {
    let text = buffer.toString('utf8');
    assert(Buffer.from(text, 'utf8').equals(buffer), 'TSV must be valid UTF-8; refusing a lossy import.');
    const bom = text.startsWith('\uFEFF');
    if (bom) text = text.slice(1);
    const endings = text.match(/\r\n|\r|\n/g) ?? [];
    assert(new Set(endings).size <= 1, 'Mixed TSV line endings require an explicit normalization before import.');
    const newline = endings[0] ?? '\n';
    const finalNewline = text.endsWith(newline);
    const lines = text.split(newline);
    if (finalNewline) lines.pop();
    assert(lines.length > 0, 'Missing TSV header.');
    return { headers: lines[0].split('\t'), rows: lines.slice(1).map(line => line.split('\t')), bom, newline, finalNewline };
}

export function columnDefinitions(headers) {
    const used = new Set();
    return headers.map((header, index) => {
        let key = header || `column-${index + 1}`;
        while (used.has(key)) key += `#${index + 1}`;
        used.add(key);
        return { key, header };
    });
}

export const rowId = order => `row-${String(order).padStart(5, '0')}`;
export function recordFromCells(cells, order, columns) {
    assert(cells.length <= columns.length, `Row ${order}: more cells than column headers.`);
    return {
        sourceId: rowId(order), order, columnCount: cells.length,
        fields: Object.fromEntries(cells.flatMap((cell, index) => cell === '' ? [] : [[columns[index].key, cell]])),
    };
}

export function cellsFromRecord(record, schema) {
    const columns = schema.columns;
    assert(Number.isInteger(record.order) && record.order >= 0 && record.sourceId === rowId(record.order), 'Record sourceId/order mismatch; row slots must remain stable.');
    assert(Number.isInteger(record.columnCount) && record.columnCount > 0 && record.columnCount <= columns.length, `${record.sourceId}: invalid columnCount.`);
    assert(record.fields && typeof record.fields === 'object' && !Array.isArray(record.fields), `${record.sourceId}: missing fields.`);
    const keys = new Set(columns.slice(0, record.columnCount).map(column => column.key));
    for (const [key, value] of Object.entries(record.fields)) {
        assert(keys.has(key), `${record.sourceId}: unknown/out-of-width column ${key}.`);
        assert(typeof value === 'string' && !/[\t\r\n]/.test(value), `${record.sourceId}/${key}: TSV cells must be strings without tabs or newlines.`);
    }
    return columns.slice(0, record.columnCount).map(column => record.fields[column.key] ?? '');
}

export function encodeTable(table) {
    const { schema, records } = table;
    const rows = records.map(record => cellsFromRecord(record, schema).join('\t'));
    const lines = [schema.columns.map(column => column.header).join('\t'), ...rows];
    return Buffer.from((schema.bom ? '\uFEFF' : '') + lines.join(schema.newline) + (schema.finalNewline ? schema.newline : ''), 'utf8');
}

export function loadTable(directory) {
    const schema = readJson(path.join(directory, 'schema.json'));
    assert(schema.schemaVersion === 1, `${directory}: unsupported table schema.`);
    assert(/^[a-z0-9-]+$/.test(schema.name), `${directory}: invalid table name.`);
    assert(Array.isArray(schema.columns) && schema.columns.length > 0, 'Missing table columns.');
    assert(new Set(schema.columns.map(column => column.key)).size === schema.columns.length, 'Duplicate schema column keys.');
    for (const column of schema.columns) assert(typeof column.key === 'string' && typeof column.header === 'string' && !/[\t\r\n]/.test(column.header), 'Invalid schema column.');
    assert(['\n', '\r\n', '\r'].includes(schema.newline), 'Invalid TSV newline.');
    assert(Array.isArray(schema.targets) && schema.targets.length > 0, 'Missing table targets.');
    const records = files(path.join(directory, 'records')).map(file => {
        assert(file.endsWith('.json'), `Unexpected record file: ${file}`);
        const record = readJson(file);
        assert(path.basename(file).startsWith(record.sourceId + '-'), `${file}: filename must retain sourceId prefix.`);
        return { ...record, file };
    }).sort((a, b) => a.order - b.order);
    records.forEach((record, index) => {
        assert(record.order === index, `${schema.name}: missing or duplicate row slot ${index}. Keep disabled/separator rows; append new slots.`);
        cellsFromRecord(record, schema);
    });
    if (schema.protectedRows !== undefined) {
        assert(Number.isInteger(schema.protectedRows) && records.length >= schema.protectedRows, `${schema.name}: existing row slots cannot be removed.`);
        const identities = records.slice(0, schema.protectedRows).map(record => [record.sourceId, ...(schema.identityColumns ?? []).map(key => record.fields[key] ?? '')]);
        assert(sha256(JSON.stringify(identities)) === schema.identitySha256, `${schema.name}: existing runtime IDs changed. Restore them or perform an explicit schema migration.`);
    }
    const identityColumns = schema.identityColumns ?? [];
    for (const field of identityColumns) assert(schema.columns.some(column => column.key === field), `${schema.name}: unknown identity column ${field}.`);
    if (identityColumns.length === 1) {
        const [field] = identityColumns;
        const values = new Map();
        for (const record of records) {
            const value = record.fields[field];
            if (value === undefined || value === '') continue;
            values.set(value, [...(values.get(value) ?? []), record.sourceId]);
        }
        for (const [value, ids] of values) {
            if (ids.length < 2) continue;
            assert(JSON.stringify(ids) === JSON.stringify(schema.legacyDuplicateIdentities?.[field]?.[value]), `${schema.name}: new duplicate identity ${field}=${value}.`);
        }
    } else if (identityColumns.length > 1) {
        const values = new Map();
        for (const record of records) {
            const tuple = identityColumns.map(field => record.fields[field] ?? '');
            if (tuple.every(value => value === '')) continue;
            const key = JSON.stringify(tuple);
            values.set(key, [...(values.get(key) ?? []), record.sourceId]);
        }
        for (const [key, ids] of values) {
            if (ids.length < 2) continue;
            assert(JSON.stringify(ids) === JSON.stringify(schema.legacyDuplicateIdentityTuples?.[key]), `${schema.name}: new duplicate identity (${identityColumns.join(', ')})=${key}.`);
        }
    }
    return { schema, records };
}

export function loadTables(root) {
    const directory = path.join(root, 'source', 'tables');
    if (!fs.existsSync(directory)) return [];
    return fs.readdirSync(directory).sort().map(name => loadTable(inside(directory, name)));
}

export function applyTableOverrides(table, rules, target) {
    const result = clone(table);
    const changes = [];
    const occupied = new Set();
    for (const rule of rules.filter(rule => rule.table === table.schema.name)) {
        assert(!rule.targets || (Array.isArray(rule.targets) && rule.targets.length > 0 && rule.targets.every(value => table.schema.targets.includes(value))), `Invalid targets in ${rule.rulePath}.`);
        if (rule.targets && !rule.targets.includes(target)) continue;
        assert(typeof rule.reason === 'string' && rule.reason.trim(), `Override requires a reason: ${rule.rulePath}`);
        const record = result.records.find(record => record.sourceId === rule.record);
        assert(record, `Missing override record ${rule.record} in ${rule.rulePath}.`);
        assert(rule.changes && Object.keys(rule.changes).length > 0, `Empty override: ${rule.rulePath}`);
        for (const [field, change] of Object.entries(rule.changes)) {
            const identity = `${record.sourceId}/${field}`;
            assert(!occupied.has(identity), `Conflicting overrides for ${identity}.`);
            occupied.add(identity);
            assert(typeof change.expect === 'string' && typeof change.value === 'string', `Override values must be strings: ${identity}`);
            assert((record.fields[field] ?? '') === change.expect, `Stale override ${rule.rulePath}: ${identity} expected ${JSON.stringify(change.expect)}, found ${JSON.stringify(record.fields[field] ?? '')}.`);
            assert(!(table.schema.identityColumns ?? []).includes(field), `Runtime overrides cannot change identity column ${field}.`);
            record.fields[field] = change.value;
            cellsFromRecord(record, table.schema);
            changes.push({ path: target, kind: 'table', record: record.sourceId, field, from: change.expect, to: change.value, rule: rule.rulePath, reason: rule.reason });
        }
    }
    return { table: result, changes };
}

export function placeholders(text) {
    return text.match(/%%|%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]*[diuoxXfFeEgGaAcspn]/g)?.filter(token => token !== '%%') ?? [];
}

export function resolveString(record, mode, locales, rulePath) {
    const allowed = new Set(['order', 'id', 'Key', 'translations', 'standardTranslations', 'standardReviewedAgainst']);
    for (const field of Object.keys(record)) assert(allowed.has(field), `${rulePath}: unknown string field ${field}.`);
    assert(Number.isInteger(record.id) && record.id >= 0 && record.id <= 65535, `${rulePath}: invalid numeric string ID.`);
    assert(typeof record.Key === 'string' && record.Key.length > 0 && !record.Key.includes('\0'), `${rulePath}: invalid string key.`);
    assert(record.translations && typeof record.translations === 'object', `${rulePath}: missing translations.`);
    const output = { id: record.id, Key: record.Key };
    const changes = [];
    for (const locale of Object.keys(record.translations)) assert(locales.includes(locale), `${rulePath}: unknown locale ${locale}.`);
    for (const locale of Object.keys(record.standardTranslations ?? {})) assert(locales.includes(locale), `${rulePath}: unknown compact locale ${locale}.`);
    for (const locale of locales) {
        const full = record.translations[locale];
        assert(typeof full === 'string' && !full.includes('\0'), `${rulePath}: invalid/missing ${locale} translation.`);
        const compact = record.standardTranslations?.[locale];
        if (compact !== undefined) {
            assert(typeof compact === 'string' && !compact.includes('\0'), `${rulePath}: invalid compact ${locale}.`);
            assert(record.standardReviewedAgainst?.[locale] === sha256(full), `${rulePath}: compact ${locale} needs review against the current full text.`);
            assert(JSON.stringify(placeholders(full)) === JSON.stringify(placeholders(compact)), `${rulePath}: compact ${locale} changes format placeholders.`);
        }
        output[locale] = mode === 'standard' && compact !== undefined ? compact : full;
        if (output[locale] !== full) changes.push({ kind: 'string', id: record.id, key: record.Key, locale, from: full, to: output[locale], rule: rulePath });
    }
    return { output, changes };
}

export function loadStrings(root, mode) {
    const directory = path.join(root, 'source', 'strings');
    if (!fs.existsSync(directory)) return [];
    const globalIds = new Set();
    return fs.readdirSync(directory).sort().map(category => {
        const location = inside(directory, category);
        const schema = readJson(path.join(location, 'schema.json'));
        assert(schema.schemaVersion === 1 && schema.category === category, `Invalid string schema: ${category}`);
        assert(Array.isArray(schema.locales) && schema.locales.join('|') === locales.join('|'), `Preserve all supported locales in ${category}.`);
        const keys = new Set();
        const entries = files(path.join(location, 'records')).map(file => ({ record: readJson(file), file }))
            .sort((a, b) => a.record.order - b.record.order);
        const changes = [];
        const rows = entries.map(({ record, file }, index) => {
            assert(record.order === index, `${file}: missing or duplicate string order ${index}.`);
            assert(path.basename(file).startsWith(`string-${String(record.id).padStart(5, '0')}-`), `${file}: filename/ID mismatch.`);
            assert(!globalIds.has(record.id), `${file}: duplicate numeric string ID ${record.id}.`);
            assert(!keys.has(record.Key), `${file}: duplicate key ${record.Key} in ${category}.`);
            globalIds.add(record.id);
            keys.add(record.Key);
            const resolved = resolveString(record, mode, schema.locales, posix(path.relative(root, file)));
            changes.push(...resolved.changes.map(change => ({ path: schema.target, ...change })));
            return resolved.output;
        });
        return { schema, rows, changes };
    });
}

export function stringReport(categories) {
    const totals = { records: 0, keyUtf8BytesWithNull: 0 };
    const byLocale = Object.fromEntries(locales.map(locale => [locale, { utf8BytesWithNull: 0, utf16leBytesWithNull: 0 }]));
    const byFile = categories.map(({ schema, rows }) => {
        let keyBytes = 0;
        for (const row of rows) {
            keyBytes += Buffer.byteLength(row.Key, 'utf8') + 1;
            for (const locale of locales) {
                assert(typeof row[locale] === 'string', `${schema.target}: missing locale ${locale}.`);
                byLocale[locale].utf8BytesWithNull += Buffer.byteLength(row[locale], 'utf8') + 1;
                byLocale[locale].utf16leBytesWithNull += Buffer.byteLength(row[locale], 'utf16le') + 2;
            }
        }
        totals.records += rows.length;
        totals.keyUtf8BytesWithNull += keyBytes;
        return { path: schema.target, records: rows.length, keyUtf8BytesWithNull: keyBytes };
    });
    return {
        status: 'source-payload-only', runtimeCapacity: null, runtimeRemaining: null, runtimeUsedPercent: null,
        explanation: 'Counts selected mod JSON records, without deduplication. UTF-8 and UTF-16LE are alternative payload calculations, not verified native allocations. Base-game/loader strings, fallback behavior, index/allocator overhead and native capacities have not been calibrated.',
        totals, byLocale, byFile,
        largestTextEntries: categories.flatMap(category => category.rows.flatMap(row => locales.map(locale => ({ path: category.schema.target, id: row.id, key: row.Key, locale, utf8BytesWithNull: Buffer.byteLength(row[locale], 'utf8') + 1 }))))
            .sort((a, b) => b.utf8BytesWithNull - a.utf8BytesWithNull).slice(0, 20),
    };
}
