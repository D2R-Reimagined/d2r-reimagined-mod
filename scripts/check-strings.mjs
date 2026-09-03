import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assert, readJson, loadStrings, stringReport, writeJson } from './lib/source.mjs';

try {
    const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
    const args = process.argv.slice(2);
    const id = args.includes('--profile') ? args[args.indexOf('--profile') + 1] : 'standard';
    assert(['standard', 'd2rl'].includes(id), 'Use --profile standard|d2rl.');
    const profile = readJson(path.join(root, `compatibility/${id}/profile.json`));
    const report = { profile: id, ...stringReport(loadStrings(root, profile.stringMode)) };
    writeJson(path.join(root, `build/reports/${id}-strings.json`), report);
    console.log(`${id}: ${report.totals.records} records, ${report.totals.keyUtf8BytesWithNull} UTF-8 key bytes including terminators.`);
    console.table(report.byLocale);
    console.log('Runtime capacity and remaining headroom: UNKNOWN (base-game resources and native allocation rules not calibrated).');
    console.log(`Report: build/reports/${id}-strings.json`);
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
