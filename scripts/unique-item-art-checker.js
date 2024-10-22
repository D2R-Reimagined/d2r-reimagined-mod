const fs = require('fs');
const path = require('path');

// Helper function to convert a name to snake_case
const toSnakeCase = (str) => {
    return str
        .replace(/[^\w\s]/g, '') // Remove non-word characters except spaces
        .replace(/\s+/g, '_') // Replace spaces with underscores
        .toLowerCase();
};

// Read the TSV file and extract the index names
const extractIndexNamesFromTSV = (tsvPath) => {
    const tsvContent = fs.readFileSync(tsvPath, 'utf-8');
    const lines = tsvContent.split('\n');

    // Extract only the index values from each line (first column)
    return lines.map(line => line.split('\t')[0].trim()).filter(name => name);
};

// Read the JSON file and extract the keys
const extractKeysFromJSON = (jsonPath) => {
    const jsonData = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));

    // Extract all keys from JSON, converting them to a set for quick lookup
    return new Set(jsonData.map(item => Object.keys(item)[0]));
};

// Compare the TSV index names with JSON keys and find missing entries
const findMissingEntries = (tsvPath, jsonPath) => {
    const tsvIndexNames = extractIndexNamesFromTSV(tsvPath);
    const jsonKeys = extractKeysFromJSON(jsonPath);

    // Convert TSV index names to snake_case and compare with JSON keys
    return tsvIndexNames
        .map(name => toSnakeCase(name))
        .filter(name => !jsonKeys.has(name));
};

// Path to your TSV and JSON files
const tsvFilePath = path.join(__dirname, '../data/global/Excel/uniqueitems.txt'); // Change 'items.tsv' to your TSV filename
const jsonFilePath = path.join(__dirname, '../data/hd/items/uniques.json'); // Change 'items.json' to your JSON filename

// Find and log missing entries
const missingEntries = findMissingEntries(tsvFilePath, jsonFilePath);
console.log('Missing entries:', missingEntries);
