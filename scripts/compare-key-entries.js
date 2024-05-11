const fs = require('fs');

// Read the files
const file1 = fs.readFileSync('../data/local/lng/strings/ui.json', 'utf8').replace(/^\uFEFF/, '');
const file2 = fs.readFileSync('../../cascs/data/data/local/lng/strings/ui.json', 'utf8').replace(/^\uFEFF/, '');

// Parse the JSON
const json1 = JSON.parse(file1);
const json2 = JSON.parse(file2);

// Convert the arrays to maps for easier lookup
const map1 = new Map(json1.map(item => [item.Key, item.id]));
const map2 = new Map(json2.map(item => [item.Key, item.id]));

// Iterate over the second map and print out entries missing in the first map
for (const [key, id] of map2) {
    if (!map1.has(key)) {
        console.log(`Missing entry: Key = ${key}, ID = ${id}`);
    }
}