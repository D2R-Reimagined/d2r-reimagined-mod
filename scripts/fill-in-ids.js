// node fill-in-ids.js

const fs = require('fs');
const path = require('path');

// Do not touch ids below this value
const SKIP_UNTIL = 30000;

// Directory that contains your JSON string files
const STRINGS_DIR = path.join(__dirname, '..', 'data', 'local', 'lng', 'strings');

// Configure each file and its starting ID range
const FILES = [
    { file: 'item-modifiers.json',  startId: 48000 },
    { file: 'item-nameaffixes.json', startId: 49000 },
    { file: 'item-names.json',      startId: 50000 },
    { file: 'item-runes.json',      startId: 53500 },
    { file: 'levels.json',          startId: 54000 },
    { file: 'monsters.json',        startId: 55000 },
    { file: 'skills.json',          startId: 56000 },
    { file: 'ui.json',              startId: 57000 },
];

function main() {
    console.log('=== Filling IDs in string JSON files ===');
    console.log('Strings dir:', STRINGS_DIR);
    console.log('Skip ids below:', SKIP_UNTIL);
    console.log('');

    for (const entry of FILES) {
        processFile(entry);
        console.log('----------------------------------------');
    }

    console.log('All done.');
}

function processFile({ file, startId }) {
    const fullPath = path.join(STRINGS_DIR, file);
    console.log(`Processing: ${fullPath}`);
    console.log(`Starting ID for this file: ${startId}`);

    let raw;
    try {
        raw = fs.readFileSync(fullPath, 'utf8');
    } catch (err) {
        console.error('  ✖ Error reading file:', err.message);
        return;
    }

    const cleaned = raw.replace(/^\uFEFF/, '').trim();

    if (!cleaned) {
        console.error('  ✖ File is empty or only BOM, skipping.');
        return;
    }

    let json;
    try {
        json = JSON.parse(cleaned);
    } catch (err) {
        console.error('  ✖ Error parsing JSON, NOT writing anything.');
        console.error('    Message:', err.message);
        return;
    }

    if (!Array.isArray(json)) {
        console.error('  ✖ JSON root is not an array, skipping.');
        return;
    }

    let currentId = startId;
    let changed = false;

    const updated = json.map((obj) => {
        if (!obj || typeof obj !== 'object') return obj;

        // Only touch numeric ids >= SKIP_UNTIL
        if (typeof obj.id === 'number' && obj.id >= SKIP_UNTIL) {
            if (obj.id !== currentId) {
                changed = true;
            }
            obj = { ...obj, id: currentId };
            currentId++;
        }

        return obj;
    });

    if (!changed) {
        console.log('  ✔ No ids changed; not writing file.');
        return;
    }

    // Write updated JSON back to file
    try {
        const out = JSON.stringify(updated, null, 4) + '\n';
        fs.writeFileSync(fullPath, out, 'utf8');
        console.log('  ✔ File written successfully.');
        console.log('  Last ID used in this file:', currentId - 1);
    } catch (err) {
        console.error('  ✖ Error writing file:', err.message);
    }
}

main();