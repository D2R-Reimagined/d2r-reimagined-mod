import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { assert, inside, files, posix, readJson, writeJson, loadTables, applyTableOverrides, encodeTable, loadStrings, stringReport, sha256 } from './source.mjs';

export function encodeStrings(category) {
    const { schema, rows } = category;
    assert(['\n', '\r\n'].includes(schema.newline) && [2, 4].includes(schema.indent), 'Invalid string output format.');
    return Buffer.from((schema.bom ? '\uFEFF' : '') + JSON.stringify(rows, null, schema.indent).replaceAll('\n', schema.newline) + (schema.finalNewline ? schema.newline : ''));
}

export function inputFiles(root, profileRoot) {
    return [...files(path.join(root, 'source')), ...files(path.join(root, 'data')), ...files(profileRoot),
        ...files(path.join(root, 'scripts')).filter(file => !file.includes(`${path.sep}tests${path.sep}`)), path.join(root, 'modinfo.json')];
}

function renderJsonTemplate(content, variables, source) {
    const value = JSON.parse(content.toString('utf8').replace(/^\uFEFF/, ''));
    function replace(node) {
        if (typeof node === 'string') {
            if (!node.includes('${')) return node;
            assert(Object.hasOwn(variables, node), `${source}: unknown template value ${node}. Templates must occupy the complete JSON string.`);
            return variables[node];
        }
        if (Array.isArray(node)) return node.map(replace);
        if (node && typeof node === 'object') return Object.fromEntries(Object.entries(node).map(([key, child]) => [key, replace(child)]));
        return node;
    }
    return Buffer.from(JSON.stringify(replace(value), null, 4) + '\n');
}

export function buildProfile(root, profileId, { verifyMigration = false } = {}) {
    assert(['standard', 'd2rl'].includes(profileId), `Unknown profile: ${profileId}`);
    const profileRoot = inside(root, `compatibility/${profileId}`);
    const profile = readJson(path.join(profileRoot, 'profile.json'));
    for (const key of Object.keys(profile)) assert(['schemaVersion', 'id', 'stringMode', 'description', 'tableOverrides', 'assetOverrides'].includes(key), `Unknown profile field: ${key}`);
    assert(profile.schemaVersion === 1 && profile.id === profileId, 'Invalid profile identity/schema.');
    assert(['standard', 'full'].includes(profile.stringMode), 'Invalid string mode.');
    assert(Array.isArray(profile.tableOverrides) && Array.isArray(profile.assetOverrides), 'Profile must declare override arrays.');
    const modInfo = readJson(path.join(root, 'modinfo.json'));
    assert(typeof modInfo.version === 'string' && modInfo.version.length > 0, 'modinfo.json must contain a version.');
    const tables = loadTables(root);
    const rules = profile.tableOverrides.map(relative => ({ ...readJson(inside(profileRoot, relative)), rulePath: `compatibility/${profileId}/${relative}` }));
    for (const rule of rules) assert(tables.some(table => table.schema.name === rule.table), `Override targets an unmigrated/unknown table: ${rule.table}`);
    const strings = loadStrings(root, profile.stringMode);
    const generated = new Map();
    const changes = [];
    function add(target, content, owner) {
        inside(root, target);
        assert(!generated.has(target.toLowerCase()), `Generated path collision: ${target}`);
        generated.set(target.toLowerCase(), { target, content, owner });
    }
    for (const table of tables) {
        for (const target of table.schema.targets) {
            assert(target.startsWith('global/excel/') && target.endsWith('.txt'), `Invalid table target: ${target}`);
            const result = applyTableOverrides(table, rules, target);
            add(target, encodeTable(result.table), `source/tables/${table.schema.name}`);
            changes.push(...result.changes);
        }
    }
    for (const category of strings) {
        assert(category.schema.target.startsWith('local/lng/strings/') && category.schema.target.endsWith('.json'), 'Invalid string target.');
        add(category.schema.target, encodeStrings(category), `source/strings/${category.schema.category}`);
        changes.push(...category.changes);
    }

    const payload = new Map(generated);
    const dataRoot = inside(root, 'data');
    for (const file of files(dataRoot)) {
        const relative = posix(path.relative(dataRoot, file));
        const content = fs.readFileSync(file);
        const existing = payload.get(relative.toLowerCase());
        if (existing) {
            assert(verifyMigration, `Two editable sources for ${relative}. Remove the migrated data/ file after verifying migration.`);
            continue;
        }
        // Developer helpers are not game assets. Preserve intentional binary assets.
        if (/\.(bat|ps1|py|mjs|bak|log)$/i.test(relative)) continue;
        payload.set(relative.toLowerCase(), { target: relative, content, owner: `data/${relative}` });
    }
    const assetTargets = new Set();
    const modAssets = new Map();
    for (const asset of profile.assetOverrides) {
        for (const key of Object.keys(asset)) assert(['scope', 'source', 'target', 'transform', 'expectSha256', 'reason'].includes(key), `Unknown asset override field: ${key}`);
        const scope = asset.scope ?? 'data';
        assert(['data', 'mod'].includes(scope), 'Asset scope must be data or mod.');
        assert(typeof asset.target === 'string' && (scope !== 'data' || !generated.has(asset.target.toLowerCase())), 'Asset overrides cannot replace generated tables/strings.');
        inside(root, asset.target);
        if (scope === 'mod') assert(profileId === 'd2rl' && asset.target.startsWith('d2rloader/') && !/^d2rloader\/(config|logs)(\/|$)/i.test(asset.target), 'Mod-scoped assets must be authored D2RLoader files, excluding runtime config/logs.');
        const identity = `${scope}/${asset.target.toLowerCase()}`;
        assert(!assetTargets.has(identity), `Conflicting asset overrides: ${asset.target}`);
        assetTargets.add(identity);
        assert(typeof asset.reason === 'string' && asset.reason.trim(), 'Asset override needs a reason.');
        const destination = scope === 'data' ? payload : modAssets;
        const before = destination.get(asset.target.toLowerCase());
        assert(asset.expectSha256 === (before ? sha256(before.content) : null), `Stale asset override: ${asset.target}`);
        const source = inside(profileRoot, asset.source);
        let content = fs.readFileSync(source);
        if (asset.transform !== undefined) {
            assert(asset.transform === 'json-template' && asset.target.endsWith('.json'), `Unsupported asset transform: ${asset.transform}`);
            content = renderJsonTemplate(content, { '${mod.version}': modInfo.version }, asset.source);
        }
        if (scope === 'mod' && asset.target === 'd2rloader/metadata.json') {
            const metadata = JSON.parse(content.toString('utf8'));
            assert(metadata.schemaVersion === 1 && metadata.metadata?.modVersion === modInfo.version
                && typeof metadata.metadata?.author === 'string' && typeof metadata.metadata?.description === 'string'
                && typeof metadata.metadata?.website === 'string' && typeof metadata.d2rloader?.version === 'string', 'Invalid generated D2RLoader metadata.json.');
        }
        destination.set(asset.target.toLowerCase(), { target: asset.target, content, owner: `compatibility/${profileId}/${asset.source}` });
        changes.push({ path: scope === 'data' ? asset.target : `mods/Reimagined/${asset.target}`, kind: 'asset', from: asset.expectSha256, to: sha256(content), rule: `compatibility/${profileId}/profile.json`, reason: asset.reason });
    }

    let migrationVerification = null;
    if (verifyMigration) {
        const migration = readJson(path.join(root, 'source/migration.json'));
        migrationVerification = migration.originalFiles.map(original => {
            const generatedFile = payload.get(original.path.replace(/^data\//, '').toLowerCase());
            assert(generatedFile, `Missing migrated output: ${original.path}`);
            const actual = generatedFile.content;
            const byteIdentical = sha256(actual) === original.sha256;
            const semanticIdentical = original.semanticSha256 ? sha256(JSON.stringify(JSON.parse(actual.toString('utf8').replace(/^\uFEFF/, '')))) === original.semanticSha256 : byteIdentical;
            assert(semanticIdentical, `Migration changed data: ${original.path}`);
            return { path: original.path, byteIdentical, semanticIdentical };
        });
    }

    const buildRoot = inside(root, 'build');
    fs.mkdirSync(buildRoot, { recursive: true });
    const output = inside(buildRoot, profileId);
    if (fs.existsSync(output)) {
        const previous = readJson(path.join(output, 'build-manifest.json'));
        assert(previous.generator === 'reimagined-source-build' && previous.profile === profileId, `Refusing to replace unrecognized output: ${output}`);
    }
    const staging = fs.mkdtempSync(path.join(buildRoot, `.${profileId}-`));
    try {
        const mpq = path.join(staging, 'mods/Reimagined/Reimagined.mpq');
        const entries = [...payload.values()].sort((a, b) => a.target < b.target ? -1 : a.target > b.target ? 1 : 0);
        for (const entry of entries) {
            const target = inside(mpq, `data/${entry.target}`);
            fs.mkdirSync(path.dirname(target), { recursive: true });
            fs.writeFileSync(target, entry.content);
        }
        const modEntries = [...modAssets.values()].sort((a, b) => a.target < b.target ? -1 : a.target > b.target ? 1 : 0);
        for (const entry of modEntries) {
            const target = inside(staging, `mods/Reimagined/${entry.target}`);
            fs.mkdirSync(path.dirname(target), { recursive: true });
            fs.writeFileSync(target, entry.content);
        }
        const modinfo = fs.readFileSync(path.join(root, 'modinfo.json'));
        fs.writeFileSync(path.join(mpq, 'modinfo.json'), modinfo);
        let commit = null;
        try { commit = execFileSync('git', ['-c', `safe.directory=${root.replaceAll('\\', '/')}`, 'rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch { /* Test fixtures do not need Git. */ }
        const manifest = {
            schemaVersion: 1, generator: 'reimagined-source-build', profile: profileId,
            sourceCommit: commit, note: 'Built from the current working tree. Commit alone does not identify uncommitted inputs; input hashes do.',
            inputs: inputFiles(root, profileRoot)
                .map(file => ({ path: posix(path.relative(root, file)), sha256: sha256(fs.readFileSync(file)) })),
            files: [...entries.map(entry => ({ path: `mods/Reimagined/Reimagined.mpq/data/${entry.target}`, sha256: sha256(entry.content), size: entry.content.length, owner: entry.owner })),
                ...modEntries.map(entry => ({ path: `mods/Reimagined/${entry.target}`, sha256: sha256(entry.content), size: entry.content.length, owner: entry.owner })),
                { path: 'mods/Reimagined/Reimagined.mpq/modinfo.json', sha256: sha256(modinfo), size: modinfo.length, owner: 'modinfo.json' }],
            changes, migrationVerification,
        };
        writeJson(path.join(staging, 'build-manifest.json'), manifest);
        writeJson(path.join(staging, 'string-budget.json'), { profile: profileId, ...stringReport(strings) });
        if (fs.existsSync(output)) fs.rmSync(output, { recursive: true });
        fs.renameSync(staging, output);
        return manifest;
    } finally {
        if (fs.existsSync(staging)) fs.rmSync(staging, { recursive: true });
    }
}
