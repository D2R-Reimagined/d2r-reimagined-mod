import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assert, inside, readJson, writeJson, resolveString, sha256, locales } from './lib/source.mjs';

try {
    const args = process.argv.slice(2);
    const relative = args.includes('--file') ? args[args.indexOf('--file') + 1] : undefined;
    assert(relative?.startsWith('source/strings/') && relative.includes('/records/') && relative.endsWith('.json'), 'Usage: node scripts/review-strings.mjs --file source/strings/<category>/records/<file>.json');
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
    const file = inside(root, relative);
    const record = readJson(file);
    const compact = Object.keys(record.standardTranslations ?? {});
    assert(compact.length > 0, 'No compact translations to mark as reviewed.');
    record.standardReviewedAgainst ??= {};
    for (const locale of compact) {
        assert(typeof record.translations[locale] === 'string', `Missing full ${locale} translation.`);
        record.standardReviewedAgainst[locale] = sha256(record.translations[locale]);
    }
    resolveString(record, 'standard', locales, relative);
    writeJson(file, record);
    console.log(`Recorded your compact-text review for ${record.Key}: ${compact.join(', ')}. This validates placeholders, not translation meaning.`);
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
