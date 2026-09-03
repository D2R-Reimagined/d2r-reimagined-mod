import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportTable } from './lib/editor.mjs';

try {
    const args = process.argv.slice(2);
    const table = args.includes('--table') ? args[args.indexOf('--table') + 1] : undefined;
    const out = args.includes('--out') ? args[args.indexOf('--out') + 1] : undefined;
    if (!table || !out) throw new Error('Usage: node scripts/export-tsv.mjs --table uniqueitems --out build/edit/uniques.txt');
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
    console.log(`Exported shared source: ${exportTable(root, table, out)}\nKeep its .source.json file beside it. Runtime overrides are not included.`);
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
