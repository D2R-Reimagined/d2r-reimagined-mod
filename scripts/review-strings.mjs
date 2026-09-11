import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assert } from './lib/source.mjs';
import { reviewString } from './lib/editor.mjs';

try {
    const args = process.argv.slice(2);
    const relative = args.includes('--file') ? args[args.indexOf('--file') + 1] : undefined;
    const rawId = args.includes('--id') ? args[args.indexOf('--id') + 1] : undefined;
    assert(relative && /^\d+$/.test(rawId ?? ''), 'Usage: node scripts/review-strings.mjs --file source/strings/<category>/records.json --id <numeric-id>');
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
    const result = reviewString(root, relative, Number(rawId));
    console.log(`Recorded your compact-text review for ${result.key}: ${result.locales.join(', ')}. This validates placeholders, not translation meaning.`);
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
