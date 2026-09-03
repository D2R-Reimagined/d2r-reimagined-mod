import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildProfile } from './lib/build.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const profile = args.includes('--all') ? ['standard', 'd2rl'] : [args[args.indexOf('--profile') + 1]];
try {
    if (!args.includes('--all') && !args.includes('--profile')) throw new Error('Usage: node scripts/build.mjs --all | --profile standard|d2rl [--verify-migration]');
    for (const id of profile) {
        const result = buildProfile(root, id, { verifyMigration: args.includes('--verify-migration') });
        console.log(`${id}: ${result.files.length} files, ${result.changes.length} compatibility changes -> build/${id}/mods/Reimagined`);
        if (result.migrationVerification) console.log(`Migration verified: ${result.migrationVerification.filter(file => file.byteIdentical).length}/${result.migrationVerification.length} files byte-identical; all table cells and string values preserved.`);
    }
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
