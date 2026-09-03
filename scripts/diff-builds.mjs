import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assert, inside, files, posix, readJson, writeJson, sha256 } from './lib/source.mjs';
import { inputFiles } from './lib/build.mjs';

try {
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
    const profiles = ['standard', 'd2rl'].map(id => {
        const directory = inside(root, `build/${id}`);
        const manifest = readJson(path.join(directory, 'build-manifest.json'));
        const currentInputs = inputFiles(root, inside(root, `compatibility/${id}`)).map(file => posix(path.relative(root, file))).sort();
        assert(JSON.stringify(currentInputs) === JSON.stringify(manifest.inputs.map(file => file.path).sort()), `Added/removed inputs since ${id} build. Rebuild both profiles.`);
        const actual = files(path.join(directory, 'mods')).map(file => posix(path.relative(directory, file))).sort();
        assert(JSON.stringify(actual) === JSON.stringify(manifest.files.map(file => file.path).sort()), `Untracked/missing files in ${id} output. Rebuild.`);
        for (const entry of manifest.files) assert(sha256(fs.readFileSync(inside(directory, entry.path))) === entry.sha256, `Modified output ${id}/${entry.path}. Rebuild.`);
        for (const entry of manifest.inputs) assert(sha256(fs.readFileSync(inside(root, entry.path))) === entry.sha256, `Stale ${id} build: ${entry.path}. Rebuild both profiles.`);
        return manifest;
    });
    const [standard, d2rl] = profiles.map(profile => new Map(profile.files.map(file => [file.path, file])));
    const differences = [...new Set([...standard.keys(), ...d2rl.keys()])].sort().flatMap(file => {
        if (standard.get(file)?.sha256 === d2rl.get(file)?.sha256) return [];
        const relative = file.replace(/^mods\/Reimagined\/Reimagined\.mpq\/data\//, '');
        const rules = profiles.flatMap(profile => profile.changes.filter(change => change.path === relative).map(change => ({ profile: profile.profile, ...change })));
        assert(rules.length > 0, `Unexplained runtime difference: ${file}`);
        return [{ path: file, standard: standard.get(file)?.sha256 ?? null, d2rl: d2rl.get(file)?.sha256 ?? null, rules }];
    });
    writeJson(path.join(root, 'build/reports/profile-diff.json'), { differences });
    console.log(`${differences.length} differing files. ${differences.length === 0 ? 'Both profiles currently generate identical game content.' : 'See build/reports/profile-diff.json for the responsible rules.'}`);
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
