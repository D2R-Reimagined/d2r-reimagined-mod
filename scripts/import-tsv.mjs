import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { importTable } from './lib/editor.mjs';

try {
    const args = process.argv.slice(2);
    const file = args.includes('--file') ? args[args.indexOf('--file') + 1] : undefined;
    if (!file) throw new Error('Usage: node scripts/import-tsv.mjs --file build/edit/uniques.txt');
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
    const changes = importTable(root, file);
    for (const change of changes) console.log(`${change.record}/${change.column}: ${JSON.stringify(change.from)} -> ${JSON.stringify(change.to)}`);
    console.log(`Imported ${changes.length} changed cells into shared source. Review the Git diff.`);
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
